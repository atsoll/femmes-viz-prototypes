


w = window.innerWidth-30
h = 500
var data_pref = "data/"

//possibly need these for timelines
var t_margin = 50

var red = '#ff0000'
var blue = '#0000ff'
//not actually the proper in between, but whatever
var purple = '#aa00ff'
var indiv_padding = 2


//cheat for timelines
var MIN_DATE = Date.parse('1687-04-08')
var MAX_DATE = Date.parse('1792-03-31')





//d3 integration taken from http://www.ng-newsletter.com.s3-website-us-east-1.amazonaws.com/posts/d3-on-angular.html
angular.module('d3', [])
  .factory('d3Service', ['$document', '$q', '$rootScope',
    function($document, $q, $rootScope) {
      var d = $q.defer();
      function onScriptLoad() {
        // Load client in the browser
        $rootScope.$apply(function() { d.resolve(window.d3); });
      }
      // Create a script tag with d3 as the source
      // and call our onScriptLoad callback when it
      // has been loaded
      var scriptTag = $document[0].createElement('script');
      scriptTag.type = 'text/javascript';
      scriptTag.async = true;
      scriptTag.src = 'https://cdnjs.cloudflare.com/ajax/libs/d3/3.5.17/d3.min.js';
      scriptTag.onreadystatechange = function () {
        if (this.readyState == 'complete') onScriptLoad();
      }
      scriptTag.onload = onScriptLoad;

      var s = $document[0].getElementsByTagName('body')[0];
      s.appendChild(scriptTag);

      return {
        d3: function() { return d.promise; }
      };
}]);

var app = angular.module('app', [ 'd3', 'nvd3']);


app.controller('ctrl', function($scope, $window, $document) {

  $scope.model = {
    seasonOverview: {},

  }



  function loadData(fname) {
    return fetch(fname).then(resp=>resp.json()).then(function(d){
      return d
    })
  }





  //the two season bar charts
  loadData(data_pref + "season_overview.json").then(function(da){

    var seasons= Object.keys(da).sort()
    let series = ["hommes", "femmes", "auteur inconnu"]
    let reps_series = series.map(function(z){return {key:z}})
    let rec_series = series.map(function(z){return {key:z}})
    for(let i=0;i<series.length;i++) {
      reps_series[i]["values"] = seasons.map(function(z){return {x:z, y:da[z][series[i]]["rep"]}})
      rec_series[i]["values"] = seasons.map(function(z){return {x:z, y:da[z][series[i]]["recettes"]}})
    }




    $scope.model.seasonOverview.reps = {
      data:reps_series,
      barOptions: {
        chart: {
          type: 'multiBarChart',
          height: 600,
          showXAxis: true,
          showYAxis: true,
          showLegend: true,
          reduceXTicks: false,
          duration: 500,
          margin : {
              top: 20,
              right: 20,
              bottom: 75,
              left: 50
          },
          clipEdge: false,
          stacked: true,
          xAxis: {
              axisLabel: 'Saison',
              axisLabelDistance: 15,
              rotateLabels: -45,

          },
          yAxis: {
              axisLabel: 'Représentations',
              axisLabelDistance: -15,
              showMinMax: true,
              tickFormat: function(d){
                  return d ;
              }
          }
        }
      }
    }

    $scope.model.seasonOverview.recs = {
      data:rec_series,
      barOptions: {
        chart: {
          type: 'multiBarChart',
          height: 600,
          showXAxis: true,
          showYAxis: true,
          showLegend: true,
          reduceXTicks: false,
          duration: 500,
          margin : {
              top: 20,
              right: 20,
              bottom: 75,
              left: 50
          },
          clipEdge: false,
          stacked: true,
          xAxis: {
              showMinMax: true,
              axisLabel: 'Saison',
              axisLabelDistance: 15,
              rotateLabels: -45,
          },
          yAxis: {
              axisLabel: 'Recette (livres)',
              axisLabelDistance: -15,
              showMinMax: true,
              tickFormat: function(d){
                    return d3.format('.02f')(d);
              },
          }
        }
      }
    }


    $scope.$apply()


  })


  loadData(data_pref + "play_lifetime.json").then(function(d){

    $scope.model.playDuration = [{key: "plays", values:d.data}]
    let colours = Object.values(d.data).map(function(x){

      if(x.genre==null){
        return 'grey'
      }
      else if(x.genre.includes("comédie")) {

        return "red"
      }
      else if(x.genre.includes("tragédie")) {
        return "blue"
      }
      return "purple"
    })

    //this is such a cheat but whatever

    $scope.model.playDurationOptions = {
      chart: {

          type: 'multiBarHorizontalChart',
          height: 7000,
          margin: {top: 25, right: 10, bottom: 20, left: 95},
          x: function(d){return d.id;},
          y: function(d){return d.diff;},
          barColor: colours,
          showControls: false,
          showValues: true,
          showLegend: false,
          stacked: false,
          duration: 500,
          groupSpacing: 0.7,
          tooltip:{
           contentGenerator: function (e) {
            let mult = e.data.diff > 1? "s" : ''
            return `<b>${e.data.titre}</b></br><i>${e.data.auth}</i></br>${e.data.min} / ${e.data.max}</br>${e.data.diff} jour${mult}`
            }
          },
          xAxis: {
            tickFormat: function(x,e){
              if(d.data[e].fem) {
                return "•"
              }
              else {
                return " "
              }
            }
          },




    }
  }
    $scope.$apply()
  })

//thi is exlusively for comparisons of similar people
//size is recette
//intensity is tickets
function timelineGroupSharedTimescale(data, id, height) {
  var svg = d3.select("#" + id)
  .append("svg")
  .attr("width", w)
  .attr("height", height)


  let indiv_height = (height-2*t_margin)/data.main.length
  let m_r = ((indiv_height - (2*indiv_padding))/3) //extra halving to make it look better

  let get_r = function(d) {
    //cheat so we don't get invisible circles
    return (Math.max(d,10)/data.max_recette)*m_r
  }

  let get_opacity = function(d) {
    //cheat so we don't get invisible circles
    return Math.max(d.billets, 10)/data.max_billets
  }

  var get_y = function(ind) {
    return t_margin + ind*indiv_height + indiv_padding + m_r
  }

  var get_colour = function(d) {
    if(d.includes("comédie")){
      return red
    }
    else if(d.includes("tragédie")) {
      return blue
    }
    return purple
  }

  var get_x =  d3.time.scale().domain([Date.parse(data.min_date), Date.parse(data.max_date)]).range([t_margin, w-t_margin])

  var make_point_label = function(po) {
    return `${po.date}
            ${po.titre}
            ${po.recette} livres
            ${po.billets} billets`
  }

  //data has to be transformed so that it's not a dict
  //add an index to make things easier
  var timelines = svg.selectAll("g")
  .data(data.main)
  .enter()
  .append("g")
  .attr("class", "indiv-timeline")
  .attr("height", indiv_height)
  .attr("width", w)
  .attr("index", function(d) {
    return d.index
  })
  .attr("id", function(d) {return "t-" + d.index.toString()})



  var lines = timelines.append("line")
  .style("stroke", "grey") //add main line
  .style("stroke-width", 0.5)
  .style("opacity", 0,8)
  .attr("class", "timeline-line")
  .attr("x1", t_margin)
  .attr("x2", w-t_margin)
  .attr("y1",  function(d){
    return get_y(d.index)
   })
   .attr("y2",  function(d){
     return get_y(d.index)
    })
  .style("z-index", -1)

  var startpoints = timelines.append("line")
  .style("stroke", "grey")
  .style("stroke-width", 0.5)
  .style("opacity", 0,8)
  .attr("class", "timeline-startpoint")//add start endpoint
  .attr("x1", t_margin)
  .attr("x2", t_margin)
  .attr("y1",  function(d){
    return get_y(d.index)-5
   })
   .attr("y2",  function(d){
     return get_y(d.index)+5
   })

   var start_text = timelines.append("svg:text")
   .attr("x", t_margin-5)
   .attr("y", function(d){
     return get_y(d.index)-10
   })
   .text(function(d){
     return data.min_date.toString()
   })
   .attr("fill", "grey")
   .style("opacity", 0,8)
   .attr("font-size", 8)

   var endpoints = timelines.append("line")
   .style("stroke", "grey")
   .style("stroke-width", 0.5)
   .style("opacity", 0,8)
   .attr("class", "timeline-endpoint")
   .attr("x1", w-t_margin)
   .attr("x2", w-t_margin)
   .attr("y1",  function(d){
     return get_y(d.index)-5
    })
    .attr("y2",  function(d){
      return get_y(d.index)+5
    })

    var end_text = timelines.append("svg:text")
   .attr("x", w-(t_margin*1.5))
   .attr("y", function(d){
     return get_y(d.index)-10
   })
   .text(function(d){
     return data.max_date.toString()
   })
   .attr("fill", "grey")
   .style("opacity", 0,8)
   .attr("font-size", 8)

   var labels = timelines.append("svg:text")
   .attr("x", 15)
   .attr("y", function(d){
     return get_y(d.index)-25
   })
   .text(function(d){
     return d.label
   })
   .attr("fill", "grey")
   .style("opacity", 0,8)
   .attr("font-size", 8)



   //this is the worst possible hack but my brain is too tired to figure this out
   for(let i=0;i<data.main.length;i++) {
     var tl = d3.select(`#t-${data.main[i].index.toString()}`)
    for(let j=0;j<data.main[i].points.length;j++) {

      tl.append("circle")
      .attr("cx",get_x(Date.parse(data.main[i].points[j].date)))
      .attr("cy", get_y(data.main[i].index))
      .attr("r", get_r(data.main[i].points[j].recette))
      .attr("stroke", function(){
        if(data.main[i].points[j].creation){
          return "black";
        }
        return "rgba(2,2,2,0)"
      })
      .attr("stroke-width", 2)
      .attr("fill", get_colour(data.main[i].points[j].genre))
      .attr("fill-opacity", get_opacity(data.main[i].points[j]))
      .append("svg:title")
      .text(make_point_label(data.main[i].points[j]))
    }
   }


   //not very d3 ish but easier than fetching
   /*for(let i=0;i<data.main.length;i++) {
     console.log(d3.select(`#t-${data.main[i].index.toString()}`))
     d3.select(`#t-${data.main[i].index.toString()}`)

     .data(data.main[i].points)
     .enter()

     .append("circle")
     .attr("cx", function(d){
       console.log("here")
       return get_x(Date.parse(d.date))
     })
     .attr("cy", get_y(data.main[i].index))
     .attr("r", function(d){
       return get_r(d.recette)
     })
     .attr("stroke", function(d){
       if(d.creation){
         return "black";
       }
       return get_colour(d.genre)
     })
     .attr("fill", function(d){
       return get_colour(d.genre)
     })
     .attr("fill-opacity", function(d){
       return get_opacity(d)
     })
     .append("svg:title")
     .text(function(d){
        return make_point_label(d)
     })

   }*/




}




  //thing I eventually have to deal with - redrawing on scaling
  //FIX THIS SO THAT IT'S SEASON WISE MAX PERC/VAL FOR RADIUS DUMBO
  //ok but global could work for smaller comps
function timelineGroupIndivTimescale(data, id, height, seasons) {

  var svg = d3.select("#" + id)
  .append("svg")
  .attr("width", w)
  .attr("height", height)


  let indiv_height = (height-2*t_margin)/data.main.length
  let m_r = (indiv_height - (2*indiv_padding))/2

  let get_r = function(d) {
    return (d.recette/max_r)*m_r
  }

  var get_y = function(ind) {
    return t_margin + ind*indiv_height + indiv_padding + m_r
  }


  var get_colour = function(d) {
    if(d.includes("comédie")){
      return red
    }
    else if(d.includes("tragédie")) {
      return blue
    }
    return purple
  }



  //data has to be transformed so that it's not a dict
  //add an index to make things easier
  var timelines = svg.selectAll("g")
  .data(data.main)
  .enter()
  .append("g")
  .attr("class", "indiv-timeline")
  .attr("height", indiv_height)
  .attr("width", w)
  .attr("index", function(d) {
    return d.index
  })
  .attr("id", function(d) {return "t-" + d.index.toString() + "-" + id})


  var lines = timelines.append("line")
  .style("stroke", "grey") //add main line
  .style("stroke-width", 0.5)
  .style("opacity", 0,8)
  .attr("class", "timeline-line")
  .attr("x1", t_margin)
  .attr("x2", w-t_margin)
  .attr("y1",  function(d){
    return get_y(d.index)
   })
   .attr("y2",  function(d){
     return get_y(d.index)
    })
  .style("z-index", -1)

  var startpoints = timelines.append("line")
  .style("stroke", "grey")
  .style("stroke-width", 0.5)
  .style("opacity", 0,8)
  .attr("class", "timeline-startpoint")//add start endpoint
  .attr("x1", t_margin)
  .attr("x2", t_margin)
  .attr("y1",  function(d){
    return get_y(d.index)-5
   })
   .attr("y2",  function(d){
     return get_y(d.index)+5
   })

   var start_text = timelines.append("svg:text")
   .attr("x", t_margin/2)
   .attr("y", function(d){
     return get_y(d.index)-10
   })
   .text(function(d){
     return d.start.toString()
   })
   .attr("fill", "grey")
   .style("opacity", 0,8)
   .attr("font-size", 8)

   var endpoints = timelines.append("line")
   .style("stroke", "grey")
   .style("stroke-width", 0.5)
   .style("opacity", 0,8)
   .attr("class", "timeline-endpoint")
   .attr("x1", w-t_margin)
   .attr("x2", w-t_margin)
   .attr("y1",  function(d){
     return get_y(d.index)-5
    })
    .attr("y2",  function(d){
      return get_y(d.index)+5
    })

    var end_text = timelines.append("svg:text")
   .attr("x", w-(t_margin*1.5))
   .attr("y", function(d){
     return get_y(d.index)-10
   })
   .text(function(d){
     return d.end
   })
   .attr("fill", "grey")
   .style("opacity", 0,8)
   .attr("font-size", 8)




  /* var circles = timelines.append("svg:text")
   .data()
   .enter()
   .append("circle")
   .attr("r", function(d){
     return get_r(d.r_value)
   })
   .attr("x", function(d){
     return get_x(d.date)
   })
   .attr("y",  get_y(d3.select(this.parentNode).attr("index")))
   .attr("fill", function(d){
     return get_colour(d.genre)
   })
   .attr("fill-opacity", 0.6)
   .attr("title", function(d){
     return d.label
   })*/





     //this is less d3 ish than hooking on to the previous statement, but makes more sense re:calculating scale

     for(let i=0;i<data.main.length;i++){
       var get_x = d3.time.scale().domain([Date.parse(data.main[i].start), Date.parse(data.main[i].end)]).range([t_margin, w-t_margin])

       d3.select(`#t-${data.main[i].index.toString()}-${id}`)//maybe change this to using string formatting
       .data(data.main[i].points)
       .append("circle")
       .attr("cx", function(d){
         return get_x(Date.parse(d.date))
       })
       .attr("cy", get_y(data.main[i].index))
       .attr("r", function(d){
         return get_r(d.r_value)
       })
       .attr("fill", function(d){
         return get_colour(d.genre)
       })
       .attr("fill-opacity", 0.6)
       .append("svg:title")
       .text(function(d){
          return d.label
       })


    }

  //gonne have 8 timelines
  //for seasons, perc of season rep + reg rec
  //for women, perc of reason rep + reg rep
  //overall rec collapsed + not
  //overall rep, collapsed + not
  //but need basics for all this shit



  }






  loadData(data_pref+ "basics.json").then(function(d1){
    $scope.model.basics = d1

    //do the stuff by season, mildly easier
    loadData(data_pref+"women_indiv_rec_by_season.json").then(function(d2){
      //format the data as needed for the timeline
      //SOMEWHERE i SWAPPED THESE AND i DON'T KNOW WHERE, SO EASIER TO JUST FUDGE IT HERE
      rec_dat = {
        max_r: d2.max_perc,
        main:[]
      }

      perc_dat = {
        max_r: d2.max_rec,
        main:[]
      }



      let groups = Object.keys(d2.main)
      groups.sort()

      //more trouble than it's worth to make polymorphic
      var make_rec_label = function(d){
        return `${d.date}\n${d.pièce} (${d.autrice})\n${d.rec} livres`
      }
      var make_perc_label = function(d) {
          return `${d.date}\n${d.pièce} (${d.autrice})\n${d.rec_perc} %`
      }

      //use loop instead of map for index reasons
      for(let i=0;i<groups.length;i++) {
        let clean_rec = {index:i, start: d1.seasons[groups[i]].start, end:d1.seasons[groups[i]].end, points:[]}
        let clean_perc = {index:i, start: d1.seasons[groups[i]].start, end:d1.seasons[groups[i]].end, points:[]}

        for(let j=0;j<d2.main[groups[i]].length;j++) {
          clean_rec.points.push({date:d2.main[groups[i]][j].date, genre:d2.main[groups[i]][j].genre, r_value:d2.main[groups[i]][j].rec, label: make_rec_label(d2.main[groups[i]][j]) })
          clean_perc.points.push({date:d2.main[groups[i]][j].date, genre:d2.main[groups[i]][j].genre, r_value:d2.main[groups[i]][j].rec_perc, label:make_perc_label(d2.main[groups[i]][j]) })
        }
        rec_dat.main.push(clean_rec)
        perc_dat.main.push(clean_perc)

      }


      //this way of structuring currently includes nothing lines
      //I kinda like this for negative knowledge reasons
      //but possible remove later
      //timelineGroupIndivTimescale(rec_dat, "season-timeline-rec", 3000, d1.seasons)
      //timelineGroupIndivTimescale(perc_dat, "season-timeline-perc", 3000, d1.seasons)



      //the timeline for the women authors and actresses
      //this is cheating but I don't want to redo the csvs
      let start_date = d1.seasons['1687-1688'].start
      let end_date = d1.seasons['1792-1793'].end
      let indiv_tl_height = 20
      let bar_height = 14
      let indiv_vert_padding = 3
      let horiz_margin = 20
      loadData(data_pref+ "actresses_length.json").then(function(d_c){
      loadData(data_pref+ "authors_length.json").then(function(d_a){
          //make the svg

        let dc=d_c.data
        let da = d_a.data

        //god this is inefficient
        for(let i=0;i<dc.length; i++){
          dc[i].index=i
        }

        for(let i=0;i<da.length; i++){
          da[i].index=i
        }




        let sing_tl_h = indiv_tl_height + 2*indiv_vert_padding

        var svg = d3.select("#career-length-tl")
        .append("svg")
        .attr("width", w)
        .attr("height", (dc.length + da.length)*(sing_tl_h))


        var get_x = d3.time.scale().domain([Date.parse(start_date), Date.parse(end_date)]).range([horiz_margin, w-horiz_margin])
        var get_y = function(ind) {
            return ind * sing_tl_h+ sing_tl_h/2
        }


        //start with the authors because they have the full timeline
        var auth_timelines = svg.selectAll("g")
          .data(da)
          .enter()
          .append("g")
          .attr("class", "indiv-timeline")
          .attr("class", "auth-tl")
          .attr("height", indiv_tl_height + 2*indiv_vert_padding)
          .attr("width", w)
          .attr("id", function(d) {return "t-author-" + d.id})

          //for auth timelines, can draw the full line (we have all the data)
        var auth_lines = auth_timelines.append("line")
          .style("stroke", "grey") //add main line
          .style("stroke-width", 0.5)
          .style("opacity", 0,8)
          .attr("class", "timeline-line")
          .attr("x1", horiz_margin)
          .attr("x2", w-horiz_margin)
          .attr("y1",  function(d){

            return get_y(d.index)
           })
           .attr("y2",  function(d){
             return get_y(d.index)
            })
          .style("z-index", -1)

          var auth_ranges = auth_timelines
          .append("rect")
          .attr("x", function(d){
            return get_x(Date.parse(d.start))
          })
          .attr("y", function(d){
            return get_y(d.index)-bar_height/2
          })
          .attr("width", function(d){
            if(d.start==d.end){
              //total hack
              return 1
            }
            return get_x(Date.parse(d.end))-get_x(Date.parse(d.start))
          })
          .attr("height", bar_height)
          .attr("fill", 'green')
          .attr("fill-opacity", 0.4)
          .attr("stroke", 'green')
          .append("title")
          .text(function(d){
            return `${d.nom} : ${d.start}-${d.end}`
          })

        var act_timelines = svg.selectAll("g")
          .data(dc)
          .enter()
          .append("g")
          .attr("class", "indiv-timeline")
          .attr("class", "com-tl")
          .attr("height", indiv_tl_height + 2*indiv_vert_padding)
          .attr("width", w)
          .attr("id", function(d) {return "t-actress-" + d.id})



        //do the first half of the actress timelines
        //for now, make red until 65

        let no_dat_cutoff = get_x(Date.parse('1765-09-09'))

        var act_no_data = act_timelines.append("line")
        .style("stroke", "red") //add main line
        .style("stroke-width", 0.5)
        .style("opacity", 0,8)
        .attr("class", "timeline-line-no-data")
        .attr("x1", horiz_margin)
        .attr("x2", no_dat_cutoff)
        .attr("y1",  function(d){
          return get_y(d.index)
         })
         .attr("y2",  function(d){
           return get_y(d.index)
          })
        .style("z-index", -1)

        var act_lines = act_timelines.append("line")
        .style("stroke", "grey") //add main line
        .style("stroke-width", 0.5)
        .style("opacity", 0,8)
        .attr("class", "timeline-line")
        .attr("x1", no_dat_cutoff)
        .attr("x2", w-horiz_margin)
        .attr("y1",  function(d){
          return get_y(d.index)
         })
         .attr("y2",  function(d){
           return get_y(d.index)
          })
        .style("z-index", -1)



        var act_ranges = act_timelines
        .append("rect")
        .attr("x", function(d){
          return get_x(Date.parse(d.start))
        })
        .attr("y", function(d){
          return get_y(d.index)-bar_height/2
        })
        .attr("width", function(d){
          if(d.start==d.end){
            //total hack
            return 1
          }
          return get_x(Date.parse(d.end))-get_x(Date.parse(d.start))
        })
        .attr("height", bar_height)
        .attr("fill", 'purple')
        .attr("fill-opacity", 0.4)
        .attr("stroke", 'purple')
        .append("title")
        .append("title")
        .text(function(d){
          return `${d.titre} ${d.pseudonyme} : ${d.start}-${d.end}`
        })




        //add the boxes in a not very d-3 ish way
        /*for(let i=0;i<dc.length;i++) {
          d3.select("t-author-" + dc[i].id)
          .data(dc[i])
          .append("g")
          .attr("class", "career-range")
          .append("rect")
          .attr("x",function(d){
            return d.start
          })
          .attr("y", get_y(dc))
          .attr("width", get_x(dc[i].end)-get_x(dc[i].start))
          .attr("height", bar_height)
          .attr("fill", 'green')
          .attr("fill-opacity", 0.4)
          .attr("stroke", 'green')
          .append("title")
          .text(`${dc[i].nom}: ${dc[i].start}-${dc[i].end}`)
        }*/

        //jeez I need a better way of doing this

        //add the boxes in a not very d-3 ish way
        /*for(let i=0;i<da.length;i++) {
          d3.select("t-actress-" + da[i].id)
          .append("g")
          .attr("class", "career-range")
          .append("rect")
          .attr("x",get_x(da[i].start))
          .attr("y", get_y(da))
          .attr("width", get_x(da[i].end)-get_x(da[i].start))
          .attr("height", bar_height)
          .attr("fill", 'purple')
          .attr("fill-opacity", 0.4)
          .attr("stroke", 'purple')
          .append("title")
          .text(`${da[i].nom}: ${da[i].start}-${da[i].end}`)
        }*/






        })
      })




    })

  /*  loadData(data_pref+"261_262_256_tl.json").then(function(d3){
      timelineGroupSharedTimescale(d3, "women-contemp-comp", 300)
    })*/

    loadData(data_pref+"outfile.json").then(function(d3){
      timelineGroupSharedTimescale(d3, "all-women-comp", 1300)
    })


  })







})//end of app
