import psycopg2
import csv
from lxml import etree
import os
import re
import json
import matplotlib.pyplot as plt
import matplotlib.dates as dates
import datetime
import numpy as np
#should these be in a config file...probably
DB_HOST = 'localhost'
DB_USER = 'postgres'
DB_PASS = 'postgres'


#for convenience
femmes = {}
women_plays=None

#to avoid math
seasons = None

crit_docs = {}
ptag = "{http://www.w3.org/1999/xhtml}p"
ntag = "{http://www.w3.org/1999/xhtml}note"
NAMESPACE ={'w': 'http://www.w3.org/1999/xhtml'}


def get_connection(name):
  con = psycopg2.connect(dbname=name, user=DB_USER, password=DB_PASS, host=DB_HOST)
  cur = con.cursor()
  return (con, cur)

#should probably see what velde did
#I'm going with the average of dow in same month over the last two seasons
def recette_attendue(date, cur):
    s_sorted = sorted(list(seasons.keys()))
    #wierd way to get the info, but whatever
    cur.execute("select saison, extract(month from date), jour from séances where date=%s", (date,))
    s, mo, j = cur.fetchone()
    #now grab the
    back = s_sorted.index(s)-3
    cur.execute("select avg(en_livres(livres,sols,deniers)) from séances join registres_recettes on id_recettes = registres_recettes.id where jour=%s and extract(month from date)=%s and saison>%s and saison <%s", (j, mo,s_sorted[back],s))
    return cur.fetchone()[0]

def get_part_value(field_id, type, dep_cur):
    part = None
    #could be less repetitive, but this is clearer
    if(type.startswith("single")):
        dep_cur.execute("select en_livres(livres, sols, deniers) from single_field_content where id=%s", (field_id,))
        part = dep_cur.fetchone()[0]
    else:
        dep_cur.execute("select parts_nb, en_livres(livres_total, sols_total, deniers_total) from parts_field_content where id=%s", (field_id,))
        pa = dep_cur.fetchone()
        part = pa[1]/pa[0] if pa[0]>0 else pa[1]
    return part


#because of the buckwild strusture of the db, I'm going with the avg or all nonzero parts in the same register
def part_attendue(registre, cur):
    cur.execute("select id, type from field_content where field_id ilike '%author_part%' and id like '{}%'".format(registre))
    #would rather not loop, but it seems safer
    res = cur.fetchall()
    if len(res)==0:
        return None
    num, tot = 0,0
    for el in res:
        val = get_part_value(el[0],el[1], cur)
        if val is not None:
            num+=1
            tot += val
    return tot/num

def plaintext(node):
  return re.sub(r'<(.+?)>', " ", re.sub(r'&#\d{3,4};', lambda x: chr(int(x[0][2:-1])) , etree.tostring(node).decode())).replace("&amp;", "&").strip()


def get_mention_list(doc_id, a_id):

  mentions = [elem for elem in crit_docs[doc_id].findall(".//w:auteur", NAMESPACE) if int(elem.get("id"))==a_id]
  res = []
  for m in mentions:
      wrapper = m
      while(True):
          if(wrapper.tag==ptag or wrapper.tag=='p' or wrapper.tag==ntag or wrapper.tag=='note'):
              break
          wrapper = wrapper.getparent()
      if wrapper.tag=='note' or wrapper.tag==ntag:
          continue
      if wrapper not in res:
          res.append(wrapper)
  return [plaintext(x) for x in res]


def fetch_extraits(doc, cur, id):
    if doc not in crit_docs:
        cur.execute("select content from documents where id = %s", (doc,))
        res = cur.fetchall()
        crit_docs[doc] = etree.fromstring(res[0][0])
    return get_mention_list(doc, id)




def indiv_stats(f, prefix, dat_cur, dep_cur, crit_cur):
    #for each perf of each play get rec, exp, dep
    #may eventually want these in the same file, but for now this'll do
    #could do dep exp, but not sure how much good it would be
    fields = ["date", "rec", "rec_exp", "dep_total", "part", "part_exp"]

    for p in femmes[f]["pieces"]:
        #not sure of the fastest way to do this, so I'm just picking one
        #shouldn't need distinct, but just to be safe
        dat_cur.execute("select distinct date from séances join représentations on id_séance = séances.id where id_pièce=%s order by date", (p,) )
        #just to have othings in order for eventual plotting
        dates = [x[0] for x in dat_cur.fetchall()]

        d_str = "({})".format(','.join(["'{}'".format(x.strftime("%Y-%m-%d")) for x in dates]))
        dat_cur.execute("select date, en_livres(livres, sols,deniers) from séances full join registres_recettes on id_recettes=registres_recettes.id where date in {} order by date".format(d_str))
        #awk but better for writing out
        rep_data = {x[0]:{"date": x[0],"rec":x[1]} for x in dat_cur.fetchall()}
        for r in rep_data:
            rep_data[r]["rec_exp"] = recette_attendue(r, dat_cur)
        #and dépenses
        dep_cur.execute("select id, date, en_livres(total_livres, total_sols, total_deniers) from page where date in {} order by date".format(d_str))
        res = dep_cur.fetchall()
        for el in res:
            rep_data[el[1]]["dep_total"] = el[2]
            #grab the part d'auteur if it exists
            dep_cur.execute("select id, type from field_content where page_id='{}' and field_id ilike '%author_part%'".format(el[0]))
            res = dep_cur.fetchall()
            part = None
            if len(res)>0:
                val = res[0]
                part = get_part_value(val[0], val[1], dep_cur)
            rep_data[el[1]]["part"] = part
            reg = el[0].split("_")[0] + "_"
            rep_data[el[1]]["part_exp"] = part_attendue(reg, dep_cur)

        with open("{}/{}.csv".format(prefix, p), 'w') as fi:
            #this duplicates but whatevs
            writer = csv.DictWriter(fi, fieldnames = fields)
            writer.writeheader()
            for r in rep_data:
                writer.writerow(rep_data[r])

        #doesn't seem to contain enough (any) notes to make it actually worth it




    #do concurrence (authors performed with)
    dat_cur.execute("""
    select t2.id_auteur, count(*) as cnt, nom from (select id_séance, représentations.id_pièce, id_auteur from représentations join attributions on représentations.id_pièce = attributions.id_pièce) as t1 join (select id_séance , représentations.id_pièce, id_auteur from représentations join attributions on représentations.id_pièce = attributions.id_pièce) as t2
    on t1.id_séance=t2.id_séance
    join auteurs on t2.id_auteur=auteurs.id
    where t1.id_pièce <> t2.id_pièce
    and t1.id_auteur = %s
    group by t2.id_auteur, nom
    order by cnt desc
    """, (f,))
    with open("{}/concurrence.csv".format(prefix), 'w') as fi:
        wr = csv.writer(fi)
        wr.writerow(["id", "nom", "reps"])
        for el in dat_cur.fetchall():
            wr.writerow(el)

    #pull critique mentions
    crit_cur.execute("""select documents.id, name, start_year, end_year, count(*) as mentions from mentions join documents on doc_id = documents.id where type='auteur' and index_id = %s
    group by documents.id, name, start_year, end_year
    order by start_year, end_year
    """, (f,))
    m_res= crit_cur.fetchall()
    ex_f = open("{}/extraits.csv".format(prefix), 'w')
    me_f = open("{}/mentions.csv".format(prefix), 'w')
    extraits = csv.writer(ex_f)
    mentions = csv.writer(me_f)
    for r in m_res:
        mentions.writerow(r)
        extr = fetch_extraits(r[0], crit_cur, f)
        for e in extr:
            extraits.writerow((r[1], e))

    ex_f.close()
    me_f.close()


def make_stats(data_cur, crit_cur, dep_cur):
     #output this just wi have it
     with open("results/durée.csv", 'w') as f:
         wr = csv.writer(f)
         wr.writerow(["id", "nom", "première_rep", "dernière_rep"])
         for el in femmes:
             wr.writerow([el] + list(femmes[el].values()))

      #indiv loop
     for f in femmes:
          data_cur.execute("select id_pièce from attributions where id_auteur=%s", (f,))
          femmes[f]["pieces"] = [x[0] for x in data_cur.fetchall()]
          dir = "results/{}".format(f)
          if not os.path.exists(dir):
              os.mkdir(dir)
          indiv_stats(f, dir,data_cur, dep_cur, crit_cur )



def write_to_json(obj, path):
    f = open("outfile.json",'w')

    f.write(json.dumps(obj))
    f.close()

#make all the stuff I need for graphics into json
#NONE OF THIS SO FAR IS USING RELATIVE VALUES (I.E. EXPECTED )
def prep_data(dat_cur):
    prefix = "graphiques/data/"
    #per season, men and women, agged recs and recettes
    res = {}
    for s in seasons:
        dat_cur.execute("""select count(*), sum(en_livres(livres, sols, deniers)), auteurs.féminin  from représentations join séances on id_séance = séances.id full join registres_recettes on id_recettes = registres_recettes.id full join attributions on attributions.id_pièce = représentations.id_pièce full join auteurs on id_auteur = auteurs.id
                            where saison = %s
                            group by auteurs.féminin
                            order by féminin""", (s,))
        dat = dat_cur.fetchall()
        l = len(dat)
        #possibly come back and change to None -- tbd
        res[s] = {"hommes":{"rep": dat[0][0], "recettes":dat[0][1]}, "femmes":{"rep": dat[1][0], "recettes":dat[1][1]} if l>1 else {"rep": 0, "recettes":0}, "auteur inconnu": {"rep": dat[2][0], "recettes":dat[2][1]} if l>2 else {"rep": 0, "recettes":0}}

    #this is for the overall gender comparison
    write_to_json(res, prefix + "season_overview.json")

    #duplicating the loop, but much cleaner code
    #this is for the timeline, women only
    #need play id to get genre, rec for readius
    res={}

    wp_str = ','.join([str(z) for z in women_plays])

    for s in seasons:
        #find all the women's plays
        dat_cur.execute("select date, id_pièce, en_livres(livres, sols, deniers), saison from séances join représentations on id_séance = séances.id full join registres_recettes on id_recettes = registres_recettes.id where saison = %s and id_pièce in ({}) order by date".format(wp_str), (s,))
        res[s] = [{"date":str(x[0]), "pièce": women_plays[x[1]]["titre"], "genre": women_plays[x[1]]["genre"], "autrice":femmes[women_plays[x[1]]["autrice"]]["nom"], "rec_perc":x[2]/seasons[s]["rec"], "rec":x[2], "season":x[3]} for x in dat_cur.fetchall()]


    write_to_json(res, prefix + "women_indiv_rec_by_season.json")

    #figure out what to compare to here
    res = {}
    for f in femmes:
        #p_str = femmes
        dat_cur.execute("select date, attributions.id_pièce, en_livres(livres, sols, deniers) from séances join représentations on id_séance = séances.id full join registres_recettes on id_recettes = registres_recettes.id join attributions on représentations.id_pièce = attributions.id_pièce where id_auteur = %s order by date", (f,))
        res[f] = [{"date":str(x[0]), "pièce": women_plays[x[1]]["titre"], "genre": women_plays[x[1]]["genre"], "autrice":femmes[f]["nom"], "rec_perc":x[2]/seasons[s]["rec"], "rec":x[2]} for x in dat_cur.fetchall()]

    write_to_json(obj, prefix + "women_indiv_rec_by_author.json")


    #circle packing for creations within a season
    #colour should be genre
    #intensity is recettes (doesn't need to be perc b/c we have size)
    #use an edge mark for women?
    #use a strange violin plot for seasons + creation impact
    #both of these are by season
    #leave crea for now

    #try doing career stats
    #can do parallel rec/rec
    #with vertical dotted lines for creations
    #try one version with rec non normalised, try another ones with bars above and below the axis for delta exp
    #this can also be used for the avgs bar chart
    all_perfs_women = {}
    for f in femmes:
        dat_cur.execute("select date, en_livres(livres, sols,deniers), case when création=date then true else false end from séances full join registres_recettes on id_recettes = registres_recettes.id join représentations on id_séance = séances.id join attributions on attributions.id_pièce = représentations.id_pièce join pièces on attributions.id_pièce=pièces.id where id_auteur = %s order by date", (f,))
        all_reps = {str(x[0]):{"rec":x[1], "crea":x[2]} for x in dat_cur.fetchall()}
        t_rec, t_exp, t_del = 0,0,0
        for r in all_reps:
            ra=recette_attendue(r, dat_cur)
            all_reps[r]["exp_rec"] = ra
            t_exp += ra
            t_rec+=all_reps[r]["rec"]
            #this could be calculated later, but it might speed things up if it doesn't have to be
            delta = all_reps[r]["rec"]-ra
            all_reps[r]["delta"] = delta
            t_del += delta
        #for bar chart, would I show total rec/expected ... makes sense if you graph reps too on the other axis
        #or just graph the avg deltas
        num_r = len(all_reps)
        all_perfs_women[f] = {"reps":all_reps, "avg_delta": t_del/num_r, "total": t_rec, "total_exp":t_exp}

    #write_to_json(all_perfs_women, prefix + "women_career_things.json")

    #this is just all perfs for the spiral
    #there is never a time where two women's plays are performed together so we're good
    dat_cur.execute("""
    select date, en_livres(livres, sols, deniers), t1.féminin or t2.féminin from (select id_séance, féminin, représentations.id_pièce from représentations join attributions atr on atr.id_pièce = représentations.id_pièce join auteurs on id_auteur = auteurs.id) as t1
    join (select id_séance, féminin, représentations.id_pièce from représentations join attributions atr on atr.id_pièce = représentations.id_pièce join auteurs on id_auteur = auteurs.id) as t2 on t1.id_séance = t2.id_séance
    join séances on séances.id = t1.id_séance
    full join registres_recettes on id_recettes = registres_recettes.id
    where t1.id_pièce < t2.id_pièce
    order by date
    """)
    #this won't be adjusted for inflation but whatever
    res = {str(x[0]):{"rec":x[1], "fem":x[2]} for x in dat_cur.fetchall()}
    write_to_json(res, prefix + "all_perfs.json")


    #try creations all time, do revenue within season as % of reveue for that whole season
    #probably do this as circles, with colours for genres and a pattern or something for women

    #grab all the creations
    dat_cur.execute("""select pièces.id, titre, genre, création, saison, bool_or(féminin) from pièces join séances on date=création join attributions on id_pièce=pièces.id join auteurs on id_auteur = auteurs.id where création is not null
                        group by pièces.id, saison
                        order by création""")
    crea_all = {x[0]: {"titre":x[1], "genre":x[2], "creation":str(x[3]), "saison":x[4], "fem":x[5]} for x in dat_cur.fetchall()}
    #could be calculated later but nah
    max_perc = 0
    max_rev =0
    to_del = []
    #inefficient but whatevs
    for el in crea_all:
        #get all the performances within the creation season
        dat_cur.execute("select sum(en_livres(livres, sols, deniers)) from séances join représentations on id_séance = séances.id join registres_recettes on id_recettes = registres_recettes.id where id_pièce = %s and saison = %s", (el, crea_all[el]["saison"]))
        rev_sum = dat_cur.fetchone()[0]
        if rev_sum is None:
            to_del.append(el)
            continue

        #want %of total rev
        perc = (rev_sum/seasons[crea_all[el]["saison"]]["rec"])*100
        crea_all[el]["rev_perc"] = perc
        crea_all[el]["rev"] = rev_sum
        if perc > max_perc:
            max_perc=perc
        if rev_sum > max_rev:
            max_rev = rev_sum
    for p in to_del:
        del crea_all[p]
    res = {"max_perc":max_perc, "max_rev":max_rev,"creations": crea_all}
    write_to_json(res, prefix + "all_creations_rev_within_season.json")



def make_auth_tl_data(auth_list, dat_cur):
    prefix = "graphiques/data/"
    min_date = None
    max_date = None
    max_recette = 0
    max_billets = 0
    dat= {"main":[]}
    for a in auth_list:
        dat_cur.execute("select nom from auteurs where id=%s", (a,))
        res = {"id":a, "label":dat_cur.fetchone()[0], "index":auth_list.index(a)}
        dat_cur.execute("select date, titre, en_livres(livres,sols,deniers) as recette, genre, date=création as crea, séances.id from séances join représentations on id_séance = séances.id  join attributions on représentations.id_pièce = attributions.id_pièce join pièces on représentations.id_pièce = pièces.id join registres_recettes on id_recettes = registres_recettes.id where id_auteur = %s order by date", (a,))
        res["points"] = [{"séance": x[5], "date":str(x[0]), "titre":x[1], "recette":x[2], "genre":x[3], "creation":x[4]} for x in dat_cur.fetchall()]
        for i in range(len(res["points"])):
            dat_cur.execute("select coalesce(sum(billets_vendus), 0) from ventes where id_séance =  %s", (res["points"][i]["séance"],))
            res["points"][i]["billets"] = dat_cur.fetchone()[0]



        #check max and min
        if min_date is None or res["points"][0]["date"]<min_date:
            min_date =res["points"][0]["date"]
        if max_date is None or res["points"][-1]["date"]>max_date:
            max_date =res["points"][-1]["date"]
        #stupidly inefficient but I don't wannna write the loop code

        loc_m_rec = max([x["recette"] for x in res["points"] if x is not None])
        loc_m_billets = max([x["billets"] for x in res["points"] if x is not None])
        if loc_m_rec > max_recette:
            max_recette = loc_m_rec
        if loc_m_billets > max_billets:
            max_billets = loc_m_billets
        dat["main"].append(res)
    dat["max_date"], dat["min_date"], dat["max_recette"], dat["max_billets"] = max_date, min_date, max_recette, max_billets
    write_to_json(dat, prefix + '_'.join([str(a) for a in auth_list]) + "_tl.json")






def make_play_dur_data(dat_cur):
    dat_cur.execute("select max(date), min(date), max(date)-min(date)+1, genre, titre, pièces.id from pièces join représentations on id_pièce = pièces.id join séances on représentations.id_séance= séances.id group by pièces.id, genre, titre order by min(date)")
    res = {"data": [{"max":str(x[0]), "min":str(x[1]), "diff":x[2], "genre":x[3], "titre":x[4], "id":x[5]} for x in dat_cur.fetchall()]}

    #have to do this separately b/c of the possibility of multiple authorship ugh
    for i in range(len(res["data"])):
        dat_cur.execute("select array_agg(nom), bool_or(féminin) from auteurs join  attributions on id_auteur = auteurs.id where id_pièce = %s", (res["data"][i]["id"],))
        dat = dat_cur.fetchone()
        res["data"][i]["auth"] = ' &'.join(dat[0]) if dat[0] is not None else "inconnu"
        res["data"][i]["fem"] = dat[1] if dat[1] is not None else False





    write_to_json(res, "data/" + "play_lifetime.json")


def replace_ppt_graphics(cur, con):
    #breakdown per 20 years, stream and grouped bar graph, representations/reps/crea
    ranges = [{"label":"1680-1700", "min":"1680-04-30", "max":"1701-03-12"}, {"label":"1701-1720", "min":"1701-04-05", "max":"1720-03-29"}, {"label":"1721-1740", "min":"1721-04-21", "max":"1740-04-02"}, {"label":"1741-1760", "min":"1741-04-10", "max":"1760-03-22"}, {"label":"1761-1780", "min":"1760-04-14", "max":"1780-03-11"}, {"label":"1781-1793", "min":"1781-04-23", "max":"1793-03-26"}]
    #genmap = lambda x:
    #get generic data
    #bucketed by season and by chunk? (b/c don't want buckets for stream)
    bucketed = [{"hommes":None, "femmes":None, "Inconnu":None}] * len(ranges)
    for i in len in ranges:
        cur.execute("""select count(*), sum(en_livres(livres, sols, deniers)), féminin from représentations join séances on id_séance = séances.id full join registres_recettes on id_recettes =registres_recettes.id
                    full join attributions on représentations.id_pièce = attributions.id_pièce full join auteurs on id_auteur = auteurs.id
                    where date>='1760-04-14' and date<='1780-03-11'
                    group by féminin""")
        #res =



def trag_crea_actes(cur):
    res = {x:{1:0, 3:0, 4:0, 5:0, 6:0} for x in range(1,13)}
    with open(data_pref + "trag_crea_actes_months.csv") as f:
        next(f)
        for l in f:
            #could habe used the proper csv reader but whatevs
            parts = l.split(",")
            res[int(float(parts[0]))][int(parts[1])]=int(parts[2])

    print(res)
    #too tired to write my own code, so mostly stolen



    x = np.arange(12)  # the label locations
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    width = 0.15  # the width of the bars
    multiplier = 0
    colours = ['#f5eb84',"#938cf5","#f78f98","#759C99","#757575"]


    fig, ax = plt.subplots()



    for ac in res[1]:
        offset = width * multiplier
        x_vals = [res[i][ac] for i in range(1,13)]
        rects = ax.bar(x + offset, x_vals, width, label=str(ac) + (" actes" if ac>1 else " acte"), color=colours[multiplier])
        #ax.bar_label(rects, padding=3)
        multiplier += 1

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel('créations')
    plt.xticks(x + width, mois)
    ax.legend(loc='upper left')
    fig.savefig("actes_crea_repart.png")

    plt.show()

def scatter(data, title, dest, ylabel=""):
    fig, ax = plt.subplots()
    for i in range(len(data)):
        plt.scatter(data[i]["x"], data[i]["y"], label=data[i]["label"])
    plt.title(title)
    plt.legend()
    plt.ylabel(ylabel)
    plt.show()
    fig.set_size_inches(16,8)
    fig.savefig(dest)
    plt.close()

def rec_recette_double_bar(data, title, dest):
    fig, ax = plt.subplots()
    ax2=ax.twinx()
    width = 0.4

    x1=  np.arange(len(data["labels"]))
    x2 = [z+width for z in x1]


    rec = ax.bar(x1, data["rec"], width = width, label="recette totale")
    rep = ax2.bar(x2, data["rep"], width = width, label="nombre de représentations", color="orange")



    ax.set_ylabel("livres")

    ax.set_xticks([x+width/2 for x in x1])
    ax.set_xticklabels(data["labels"], rotation="90")

    #plt.tight_layout()

    fig.legend()
    plt.title(title)



    #change y limits to give more room:
    #this is taken from https://stackoverflow.com/questions/24183101/bar-plot-with-two-bars-and-two-y-axis, possibly delete
    """
    scale=1.1
    max_y_lim = max(vals)*scale
    min_y_lim = min(vals)
    ax.set_ylim(min_y_lim, max_y_lim);
    max_y_lim2 = max(vals2)*scale
    min_y_lim = min(vals2)
    ax2.set_ylim(min_y_lim2, max_y_lim2)
    """

    fig.subplots_adjust(bottom=0.5)
    plt.show()



def cenie(cur, pref, ccur):
    #other plays created in the same season
    #double axis of reps recettes

    #data for line chart, could make a cumulative bar chart instead
    #normally not safe to go off of title but here it's fine
    cur.execute("select date, titre, en_livres(livres,sols,deniers) from pièces join représentations on id_pièce = pièces.id join séances on id_séance = séances.id full join registres_recettes rr on séances.id_recettes=rr.id where  saison(création)='1750-1751' order by date")
    res = {}
    for elem in cur.fetchall():
        if elem[1] not in res:
            res[elem[1]]=[]

        res[elem[1]].append({"date":elem[0], "rec":float(elem[2])})

    #scatter
    dat = []
    for k in res:
        x = [z["date"] for z in res[k]]
        y = [z["rec"] for z in res[k]]
        dat.append({"x":x, "y":y, "label":k})
    #scatter(dat, "Trajectoires des créations de la saison 1750-1751", pref+"cénie_meme_saison_comp", "recette (livres)")

    dat = {"labels":[], "rec":[], "rep":[]}
    #now do cumulative grouped bar with double axis? for reps/recettes
    cur.execute("select titre, id_pièce, sum(en_livres(livres,sols,deniers)), count(*) from pièces join représentations on id_pièce = pièces.id join séances on id_séance = séances.id  full join registres_recettes rr on séances.id_recettes=rr.id where  saison(création)>='1748-1749' and saison(création)<='1751-1752' group by id_pièce, titre")
    for elem in cur.fetchall():
        dat["labels"].append(elem[0])
        dat["rec"].append(elem[2])
        dat["rep"].append(elem[3])

    #rec_recette_double_bar(dat, "Succès des pièces créées de la saison 1748-1749 à la saison 1751-1752", "crea_48_52")

    #50-70 times, 1750-1751 1769-1770
    cur.execute("""select * from(
    select titre, id_pièce, sum(en_livres(livres,sols,deniers)), count(*) as reps from pièces join représentations on id_pièce = pièces.id join séances on id_séance = séances.id
    full join registres_recettes rr on séances.id_recettes=rr.id
    where  saison>='1749-1750' and saison<='1771-1772'
    group by id_pièce, titre) as t
    where reps >49 and reps <71
    order by titre""")

    dat = {"labels":[], "rec":[], "rep":[]}
    for elem in cur.fetchall():
        dat["labels"].append(elem[0])
        dat["rec"].append(elem[2])
        dat["rep"].append(elem[3])

    #rec_recette_double_bar(dat, "Succès des pièces jouées 50-70 fois entre les saisons 1750-1751 et 1770-1771", "50_70")

    #all the auth with crea between 48 & 52
    cur.execute("select distinct auteurs.id, nom from  attributions join auteurs on id_auteur = auteurs.id join pièces on pièces.id= id_pièce where saison(création)>='1748-1749' and saison(création)<='1751-1752'")
    a_l = {x[0]:x[1] for x in cur.fetchall()}
    comp_auth_mentions(a_l, ccur, 1748, 1752, "Mentions d'auteurs avec nouvelles créations dans la press périodique, 1748-1752")





def comp_auth_mentions(authlist, cur, start, end, title):
    res = {}
    for a in authlist:
        cur.execute("select  start_year, count(*) from documents join mentions on doc_id = documents.id where type='auteur' and entity_id =%s and start_year>=%s and end_year<=%s group by start_year", (a,start, end))
        da = cur.fetchall()
        if len(da)>0:
            res[a] = {"x":[], "y":[]}
            for elem in da:
                res[a]["x"].append(elem[0])
                res[a]["y"].append(elem[1])

    print(res)
    fig, ax = plt.subplots()
    for k in res:
        plt.plot(res[k]["x"], res[k]["y"], label=authlist[k])

    plt.legend()
    plt.title(title)
    plt.show()


def associate_auth_parts(date, cur):
    cur.execute("select titre, nom, création, genre from pièces join représentations on id_pièce = pièces.id join séances on id_séance = séances.id  join attributions on attributions.id_pièce = pièces.id join auteurs on id_auteur=auteurs.id where date = %s", (date,))
    people = cur.fetchall()
    #this is not accounting for multiple people needing to be given parts, as I'm skipping over those (for good math reasons)
    res = [{"pièce":x[0], "auteur":x[1], "diff":date-x[2], "genre":x[3]} for x in people if x[2] is not None]
    if len(res)==0:
        return None
    min_diff = 0
    for i in range(1, len(res)):
        if res[i]["diff"]< res[min_diff]["diff"]:
            min_diff = i
    del res[min_diff]["diff"]
    return res[min_diff]


def top_50_auth_parts(dcur, cur):
    dcur.execute("select date,annotation, ((livres*240)+(sols * 12)+ deniers)::float/240 from view_expenses where name ilike '%aut%'  and livres > 0 and date is not null order by livres desc limit 60")
    with open("results/top_50_parts.csv", 'w') as f:
        lines =0
        writer = csv.writer(f)
        for elem in dcur.fetchall():
            if lines==50:
                break
            if len(elem[1])>0:
                continue
            auth = associate_auth_parts(elem[0], cur)
            if auth is None:
                print(elem[0])
                continue
            writer.writerow([elem[0], elem[2]] + list(auth.values()))




def seldom_performed(cur):
    ranges = [{"label":"1680-1700", "min":"1680-04-30", "max":"1701-03-12"}, {"label":"1701-1720", "min":"1701-04-05", "max":"1720-03-29"}, {"label":"1721-1740", "min":"1721-04-21", "max":"1740-04-02"}, {"label":"1741-1760", "min":"1741-04-10", "max":"1760-03-22"}, {"label":"1761-1780", "min":"1760-04-14", "max":"1780-03-11"}, {"label":"1781-1793", "min":"1781-04-23", "max":"1793-03-26"}]

    #want to include 21+ as a bar so as to get a sense of perspective
    res = {r["label"]: {"1-5":0, "6-10":0, "11-15":0, "16-20":0, "21+":0} for r in ranges}


    for r in ranges:
        cur.execute("""select id_pièce, count(*) as cnt from séances join représentations on id_séance = séances.id
                    where date >= %s and date <= %s
                    group by id_pièce""", (r["min"], r["max"]))

        #this is a really gross way to do this, but anyway
        for elem in cur.fetchall():
            times = elem[1]
            if times<5:
                res[r["label"]]["1-5"] +=1
            elif times < 11:
                res[r["label"]]["6-10"] +=1
            elif times < 16:
                res[r["label"]]["11-15"] +=1
            elif times< 21:
                res[r["label"]]["16-20"] +=1
            else:
                res[r["label"]]["21+"] +=1


    colours = ['#f5eb84',"#938cf5","#f78f98","#759C99","#757575"]

    xvals = list(res.keys())
    segments = list(res[xvals[0]].keys())
    formatted_dat = {s:[res[i][s] for i in xvals] for s in segments}

    #try it as a stramgraph
    #stolen from documentaion
    #this one would probably make more sense by decade, but anyway
    fig, ax = plt.subplots()
    ax.stackplot(xvals, formatted_dat.values(),
                 labels=[x+ " fois" for x in segments], alpha=0.6, colors=colours)
    plt.legend()
    #ax.legend(loc='upper left', reverse=True)
    #this title sucks
    ax.set_ylabel('Pièces')

    plt.show()
    plt.close()


    #do it as a stacked grouped bar chart instead
    fig, ax = plt.subplots()
    multiplier = 0
    width = 0.15
    x=np.arange(len(xvals))
    for d in formatted_dat:
        offset = width * multiplier
        rects = ax.bar(x + offset, formatted_dat[d], width, label= d + " fois", color=colours[multiplier])
        #ax.bar_label(rects, padding=3)
        multiplier += 1

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel('Pièces')
    plt.xticks(x + width, xvals)
    ax.legend(loc='upper left')
    #fig.savefig("actes_crea_repart.png")

    plt.show()










def static_things(cur, ccur):
    if not os.path.exists("./static_viz"):
        os.mkdir("static_viz")

    dest_pref = "static_viz/"

    #bar graph trag crea breakdown
    #trag_crea_actes(cur)
    #cenie(cur, dest_pref, ccur)
    seldom_performed(cur)


#probably try actually using pandas...
def main():
  global femmes
  global seasons
  global women_plays
  data_con, data_cur = get_connection('rcf_thesis')
  crit_con, crit_cur = get_connection('rcf_critique')
  dep_con, dep_cur = get_connection('rcf_depenses')

  if not os.path.exists("results"):
      os.mkdir("results")

  #there's deffo a more efficient query to this w/o doubling up pn function calc
  data_cur.execute("select saison, sum(coalesce(en_livres(livres, sols, deniers), 0)), max(coalesce(en_livres(livres, sols, deniers), 0)), min(date), max(date) from séances full join registres_recettes rr on id_recettes = rr.id group by saison")
  seasons = {x[0]:{"rec":float(x[1]), "max_rec":float(x[2]), "max_perc":float(x[2])/float(x[1]), "start": x[3], "end":x[4]} for x in data_cur.fetchall() }


  data_cur.execute("""select auteurs.id, nom, min(date) ,max(date) from attributions join auteurs on id_auteur = auteurs.id join représentations on représentations.id_pièce = attributions.id_pièce join séances on id_séance = séances.id
    where féminin = true
    group by auteurs.id, nom""")
  femmes = {x[0]:{"nom":x[1], "start":x[2], "end":x[3]} for x in data_cur.fetchall()}

  #there are better ways to do this, but to simplify shit
  data_cur.execute("select pièces.id, titre, genre, id_auteur, création from pièces join attributions on id_pièce = pièces.id join auteurs on id_auteur = auteurs.id where féminin = true")
  #probs review casting
  women_plays = {x[0]: {"titre":x[1], "genre":x[2], "autrice":x[3], "creation":x[4]} for x in data_cur.fetchall()}

  basics = {
    "authors": femmes,
    "seasons": seasons,
    "plays": women_plays
  }



  #make_stats(data_cur, crit_cur, dep_cur)
  #prep_data(data_cur)

  #tidy up for json serializing
  for el in basics["authors"]:
    basics["authors"][el]["start"] = str(basics["authors"][el]["start"])
    basics["authors"][el]["end"] = str(basics["authors"][el]["end"])
  for p in basics["plays"]:
    basics["plays"][p]["creation"] = str(basics["plays"][p]["creation"])
  for s in seasons:
    basics["seasons"][s]["start"] = str(basics["seasons"][s]["start"])
    basics["seasons"][s]["end"] = str(basics["seasons"][s]["end"])




  #write_to_json(basics , "graphiques/data/basics.json")
  l =  list(femmes.keys())
  l.sort(key=lambda x:femmes[x]["start"])
  print([femmes[x] for x in l])
  make_auth_tl_data(l, data_cur)
  #make_play_dur_data(data_cur)
  #static_things(data_cur, crit_cur)
  #top_50_auth_parts(dep_cur, data_cur)





main()
