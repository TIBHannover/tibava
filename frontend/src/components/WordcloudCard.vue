<template>
  <v-card ref="parent" class="parent" fluid :items="transcripts" elevation="0"
    :class="['d-flex', 'flex-column', 'pa-2', 'ma-4']">
    <v-card v-if="transcripts.length == 0" flat>
      <span>There is no transcript. Create it with the <em>Speech Recognition
          (whisper)</em> pipeline.
      </span>
    </v-card>
    <div v-else>
      <div ref="wordcloudContainer" class="wordcloudContainer"></div>
      <v-select style="width: 30%;" v-if="transcripts.length > 0" v-model="stopword_selection" :items="stopword_options"
        label="Select stopwords to be removed" item-text="name" item-value="id" persistent-hint multiple></v-select>
    </div>
  </v-card>
</template>

<script>
import TimeMixin from "../mixins/time";
import * as d3 from 'd3';
import cloud from 'd3-cloud';
import { mapStores } from "pinia";
import { useTimelineSegmentAnnotationStore } from "@/store/timeline_segment_annotation";

export default {
  mixins: [TimeMixin],
  data() {
    return {
      layout: null,
      containerHeight: 0,
      containerWidth: 0,
      stopword_selection: ['Englisch'],
      stopword_options: ['Englisch', 'Deutsch']
    };
  },
  mounted() {
    this.$nextTick(() => {
      if (this.$refs.wordcloudContainer) {
        this.containerWidth = this.$refs.wordcloudContainer.offsetWidth;
        this.containerHeight = this.$parent.$parent.$el.clientHeight - 100;
        this.createWordCloud();
      }
    });
  },
  methods: {

    createWordCloud() {
      const all_words = [];
      for (var transcript of this.transcripts) {
        for (var word of transcript.name.split(" ")) {
          if (word.endsWith(',') || word.endsWith('.')) {
            word = word.slice(0, -1);
          }
          all_words.push(word.toLowerCase());
        }
      }


      // filter out stopwords
      const { removeStopwords, deu, eng } = require('stopword');
      var filteredText = all_words;
      for (const lan of this.stopword_selection) {
        if (this.stopword_selection.includes(lan)) {
          filteredText = removeStopwords(filteredText, eng);
        }
        if (this.stopword_selection.includes(lan)) {
          filteredText = removeStopwords(filteredText, deu);
        }

      }


      // count words
      var dictionary = {};
      const custom_filter = ["", "..", ".", "?", "!"]

      filteredText.forEach((word) => {
        if (Object.prototype.hasOwnProperty.call(dictionary, word)) {
          dictionary[word]++;
        } else if (!custom_filter.includes(word)) {
          dictionary[word] = 1;
        }
      });

      // Set the desired number of words to visualize
      const num_words = 40;

      var words = Object.entries(dictionary)
        .sort((a, b) => b[1] - a[1]) // Sort the entries by count in descending order
        .slice(0, num_words) // Take the top `num_words` entries
        .map(([word, count]) => ({ // assign each word a number according to how often it appears
          text: word,
          count: count,
        }));

      const max = words[0].count;
      const desired_max = 100;

      // map all font-sizes to a good size, where the maximum is 17
      words.map((w) => {
        w.count = w.count / max * desired_max;
      });

      this.layout = cloud()
        .size([this.containerWidth, this.containerHeight])
        .words(words)
        .padding(8)
        .rotate(function () { return 0 })
        // .rotate(function () { return ~~((2 * Math.random() - 1)) }) add this if you want some rotation in the words
        .fontSize((d) => d.count)
        .on('end', this.drawWordCloud);

      this.layout.start();
    },
    drawWordCloud(words) {
      const colorScale = d3.scaleOrdinal(d3.schemeTableau10);
      d3.select(this.$refs.wordcloudContainer)
        .append('svg')
        .attr('width', this.containerWidth)
        .attr('height', this.containerHeight)
        .append("g")
        .attr("transform", "translate(" + this.layout.size()[0] / 2 + "," + this.layout.size()[1] / 2 + ")")
        .selectAll("text")
        .data(words)
        .enter().append("text")
        .style("font-family", "Arial")
        .style("font-size", function (d) { return d.size + "px"; })
        .style("fill", function (d, i) { return colorScale(i); })
        .attr("text-anchor", "middle")
        .attr("transform", function (d) {
          return "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")";
        })
        .text(function (d) { return d.text; });
    }
  },
  computed: {
    transcripts() {
      return this.timelineSegmentAnnotationStore.transcriptSegments;
    },
    ...mapStores(useTimelineSegmentAnnotationStore),
  },
  watch: {
    stopword_selection() {
      d3.select(this.$refs.wordcloudContainer).select('svg').remove();
      this.createWordCloud();
    },
  }
};
</script>

<style>
.v-window {
  height: 100%;
  width: 100%
}
</style>