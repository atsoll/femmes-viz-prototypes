import psycopg2
import csv
from lxml import etree
import os
import re
import json
import matplotlib.pyplot as plt
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
    with open(path, 'w') as f:
        f.write(json.dumps(obj))

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
            dat_cur.execute("select sum(billets_vendus) from ventes where id_séance =  %s", (res["points"][i]["séance"],))
            res["points"][i]["billets"] = dat_cur.fetchone()[0]

        #check max and min
        if min_date is None or res["points"][0]["date"]<min_date:
            min_date =res["points"][0]["date"]
        if max_date is None or res["points"][-1]["date"]>max_date:
            max_date =res["points"][-1]["date"]
        #stupidly inefficient but I don't wannna write the loop code
        loc_m_rec = max([x["recette"] for x in res["points"]])
        loc_m_billets = max([x["billets"] for x in res["points"]])
        if loc_m_rec > max_recette:
            max_recette = loc_m_rec
        if loc_m_billets > max_billets:
            max_billets = loc_m_billets
        dat["main"].append(res)
    dat["max_date"], dat["min_date"], dat["max_recette"], dat["max_billets"] = max_date, min_date, max_recette, max_billets
    write_to_json(dat, prefix + '_'.join([str(a) for a in auth_list]) + "_tl.json")






def make_play_dur_data(dat_cur):
    dat_cur.execute("""select max(date), min(date), max(date)-min(date)+1,fem, genre, titre from (
                        select bool_or(féminin) as fem, pièces.id as pid, genre, titre, représentations.id_séance as s from pièces join représentations on id_pièce = pièces.id join attributions on attributions.id_pièce = pièces.id join auteurs on id_auteur = auteurs.id
                        group by pièces.id, représentations.id) as t
                        join séances on s= séances.id
                        group by pid, titre, fem, genre
                        order by min(date)""")
    res = {"data": [{"max":str(x[0]), "min":str(x[1]), "diff":x[2], "fem":x[3], "genre":x[4], "titre":x[5]} for x in dat_cur.fetchall()]}

    #render in matplotlib



    write_to_json(res, "data/" + "play_lifetime.json")






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
  #make_auth_tl_data([261, 262, 256], data_cur)
  make_play_dur_data(data_cur)





main()
