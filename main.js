


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




  //thing I eventually have to deal with - redrawing on scaling
function timelineGroupIndivTimescale(data, id, height) {

  var svg = d3.select("#" + id)
  .append("svg")
  .attr("width", w)
  .attr("height", height)

  console.log(svg)

  let indiv_height = (height-2*t_margin)/data.main.length
  let m_r = (indiv_height - (2*indiv_padding))/2
  console.log(data.max_r, data.main)

  let get_r = function(r_val) {
    console.log(r_val, data.max_r)
    return (r_val/data.max_r)*m_r
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
      timelineGroupIndivTimescale(rec_dat, "season-timeline-rec", 3000)
      timelineGroupIndivTimescale(perc_dat, "season-timeline-perc", 3000)




    })
  })
})//end of app
