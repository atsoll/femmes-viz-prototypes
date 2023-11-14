data_pref = "data/"
import matplotlib.pyplot as plt
import numpy as np
import psycopg2
import os

#I really need to quit it with the globals but whatever
con = psycopg2.connect(dbname='rcf_thesis', user='postgres', password='postgres', host='localhost')
cur = con.cursor()

def trag_crea_actes():
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
        print(x_vals)
        rects = ax.bar(x + offset, x_vals, width, label=str(ac) + (" actes" if ac>1 else " acte"), color=colours[multiplier])
        #ax.bar_label(rects, padding=3)
        multiplier += 1

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax.set_ylabel('créations')
    plt.xticks(x + width, mois)
    ax.legend(loc='upper left')
    fig.savefig("actes_crea_repart.png")

    plt.show()





def main():
    #avg # of crea per author
    #270 is Anonyme
    cur.execute("""select id_auteur, nom, count(*), féminin as n from attributions join pièces on id_pièce = pièces.id join auteurs on id_auteur = auteurs.id where création is not null group by id_auteur, nom""")

    crea = [{"id":x[0],"nom":x[1], "num":x[2], "fem":x[3]} for x in cur.fetchall()]
    avg = [x["num"] for x in crea if x["id"]!=270]

    if not os.path.exists("./static_viz"):
        os.mkdir("static_viz")

    dest_pref = "static_viz/"







main()
