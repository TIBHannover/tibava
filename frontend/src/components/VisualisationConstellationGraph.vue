<template>
  <v-row>
    <v-col cols="3">
      <v-btn class="my-3 d-print-block mx-auto" :disabled="loading" @click="renderGraph"
        style="display: block !important">Render Graph</v-btn>
      <div style="max-height: 700px" class="overflow-y-auto">
        <h5 class="mt-6 subtitle-2">Filter</h5>
        <v-list dense>
          <v-list-item>
            <v-list-item-content>
              <v-list-item-title>Minimum Cluster Size</v-list-item-title>
            </v-list-item-content>
            <v-list-item-action>
              <v-text-field v-model="min_node" hide-details step="1" single-line type="number"
                label="Minimum Cluster Size" min="1" style="width: 60px"></v-text-field>
            </v-list-item-action>
          </v-list-item>
          <v-list-item>
            <v-list-item-content>
              <v-list-item-title>Minimum Relations</v-list-item-title>
            </v-list-item-content>
            <v-list-item-action>
              <v-text-field v-model="min_edge" hide-details step="1" single-line type="number" label="Minimum Relations"
                min="1" style="width: 60px"></v-text-field>
            </v-list-item-action>
          </v-list-item>
          <v-list-item>
            <v-list-item-content>
              <v-list-item-title>Aggregation</v-list-item-title>
            </v-list-item-content>
            <v-list-item-action>
              <v-switch class="shot-aggregation-switch" v-model="shot_aggregation" label="Shots">
                <template #prepend>
                  <v-label class="pt-1">Frames</v-label>
                </template>
              </v-switch>
            </v-list-item-action>
          </v-list-item>
        </v-list>
        <h5 v-if="Object.keys(clusterSettings).length > 0" class="mt-6 subtitle-2">Clustering</h5>
        <v-list dense>
          <v-list-item v-for="(cluster, id) in clusterSettings" :key="id">
            <v-list-item-action>
              <v-checkbox v-model="cluster.active"></v-checkbox>
            </v-list-item-action>
            <v-list-item-content>
              <v-list-item-title :class="{ 'grey--text': !cluster.active }">{{ cluster.name }}</v-list-item-title>
            </v-list-item-content>
            <v-list-item-action>
              <v-menu :disabled="!cluster.active">
                <template v-slot:activator="{ on }">
                  <v-btn disable icon x-small :color="cluster.color" class="mr-1" v-on="on">
                    <v-icon>{{ "mdi-palette" }}</v-icon>
                  </v-btn>
                </template>
                <v-card>
                  <v-card-text class="pa-0">
                    <v-color-picker v-model="cluster.color" flat />
                  </v-card-text>
                </v-card>
              </v-menu>
            </v-list-item-action>
          </v-list-item>
        </v-list>
        <h5 v-if="visibleTimelines.length > 0" class="mt-6 subtitle-2">Timelines</h5>


        <v-list>
          <v-list-item v-for="timeline in visibleTimelines" :key="timeline.id" style="flex-wrap: wrap">
            <v-list-item-action>
              <v-checkbox v-model="timeline.active"></v-checkbox>
            </v-list-item-action>
            <v-list-item-content>
              <v-list-item-title :class="{ 'grey--text': !timeline.active }">{{ timeline.name }}</v-list-item-title>
            </v-list-item-content>
            <v-list-item-action>
              <v-menu :disabled="!timeline.active">
                <template v-slot:activator="{ on }">
                  <v-btn disable icon x-small :color="timeline.color" class="mr-1" v-on="on">
                    <v-icon>{{ "mdi-palette" }}</v-icon>
                  </v-btn>
                </template>
                <v-card>
                  <v-card-text class="pa-0">
                    <v-color-picker v-model="timeline.color" flat />
                  </v-card-text>
                </v-card>
              </v-menu>
            </v-list-item-action>
            <v-list-item-action>
              <v-text-field :disabled="!timeline.active" v-model="timeline.threshold" hide-details step="0.1"
                single-line type="number" min="0" max="1" style="width: 60px"></v-text-field>
            </v-list-item-action>
            <v-list-item-action class="ms-2">
              <v-btn disable icon x-small class="ml-1" @click="timeline.showPlot = !timeline.showPlot">
                <v-icon> mdi-chart-scatter-plot </v-icon>
              </v-btn>
            </v-list-item-action>
            <VisualizationGraph v-if="timeline.showPlot" :threshold="timeline.threshold" showLegend="false"
              plotType="scatter" :timelineId="timeline.id" style="max-width: 20vw; max-height: 400px">
            </VisualizationGraph>
          </v-list-item>
        </v-list>
      </div>
    </v-col>
    <v-col cols="9" style="position: relative;">
      <div ref="visualizationTimelineConstellationGraph" style="min-height: 500px; height: 95%"></div>
      <div v-if="loading" class="text-center pt-10"
        style="height: 95%; background-color: white; top:0; width: 100%; z-index: 2; position: absolute;">
        <div class="spinner">
          <i class="mdi mdi-loading mdi-spin"></i>
        </div>
        <div class="loading-text">Loading...</div>
      </div>
    </v-col>
  </v-row>
</template>

<script>
import { mapStores } from "pinia";
import { useTimelineStore } from "@/store/timeline";
import { useShotStore } from "@/store/shot";
import { useClusterTimelineItemStore } from "../store/cluster_timeline_item";
import { Network } from "vis-network";
import { DataSet } from "vis-data";
import VisualizationGraph from "./VisualizationGraph.vue";
import Vue from "vue";


export default {
  data() {
    return {
      timelineSettings: {},
      clusterSettings: {},
      network: null,
      loading: false,
      min_node: 3,
      min_edge: 3,
      shot_aggregation: true,
    };
  },
  components: { VisualizationGraph },
  mounted() {
    this.updateTimelineSettings();
    this.updateClusterSettings(this.latestFaceClustering, 'Face Clustering');
    this.updateClusterSettings(this.latestPlaceClustering, 'Place Clustering');
    this.renderGraph();
  },
  methods: {
    updateTimelineSettings() {
      for (let settings of Object.values(this.timelineSettings)) {
        settings.visible = false;
      }
      for (let timeline of this.timelines) {
        if (!(timeline.id in this.timelineSettings)) {
          Vue.set(this.timelineSettings, timeline.id, {
            active: false,
            threshold: 0.5,
            id: timeline.id,
            name: timeline.name,
            // visible needed as timelines are briefly deleted and then reinserted
            // when updating the store and we want to persist the setting
            visible: true,
            color: '#ae1313',
            showPlot: false
          });
        } else {
          this.timelineSettings[timeline.id].visible = true;
        }
      }
    },
    updateClusterSettings(clustering, name) {
      const clusterData = clustering.map(c => ({
        name: c.name,
        id: c.id,
        timestamps: c.items.map(i => i.time),
      }));
      if (name in this.clusterSettings) {
        Vue.set(this.clusterSettings[name], 'data', clusterData);
      } else {
        Vue.set(this.clusterSettings, name, {
          name: name,
          data: clusterData,
          color: '#ae1313',
          active: false
        });
      }
    },
    renderGraph() {
      this.loading = true;
      const options = {
        nodes: {
          shape: 'dot',
          font: { size: 25, },
          borderWidth: 4,
          shadow: true,
          scaling: { max: 50 }
        },
        edges: {
          length: 300,
          smooth: { forceDirection: "none" }
        },
      };
      if (this.network) {
        this.network.destroy()
      }
      this.$nextTick(() => {
        const container = this.$refs.visualizationTimelineConstellationGraph;
        this.network = new Network(container, this.getConstellations(), options);
        this.network.on('afterDrawing', () => { this.loading = false; });
      });
    },
    calcTimelineOverlap(timestamps1, timestamps2) {
      if (this.shot_aggregation) {
        return this.shotStore.shots.map(s => timestamps1.filter(t => s.start <= t && t <= s.end).length > 0 &&
          timestamps2.filter(t => s.start <= t && t <= s.end).length > 0)
          .filter(v => v)
          .length;
      } else { // frame based
        return timestamps1.filter(t => timestamps2.includes(t)).length;
      }
    },
    countAppearance(timestamps) {
      if (this.shot_aggregation) {
        return this.shotStore.shots.map(s => timestamps.filter(t => s.start <= t && t <= s.end))
          .filter(ys => ys.length > 0)
          .length;
      } else { // frame based
        return timestamps.length;
      }
    },
    getConstellations() {
      const activeTimelines = Object.values(this.timelineSettings)
        .filter(t => t.active && t.visible)
        .map((tSetting) => {
          const timeline = this.timelines.find(i => i.id == tSetting.id);
          tSetting.timestamps = timeline.plugin.data.time.filter((time, index) => timeline.plugin.data.y[index] >= tSetting.threshold);
          return tSetting;
        });
      const clusterTimelines = Object.values(this.clusterSettings)
        .filter(c => c.active)
        .map(c => {
          c.data.forEach(i => i.color = c.color)
          return c.data
        })
        .flat(1)
        .concat(activeTimelines);
      const nodes = new DataSet(
        clusterTimelines.map((t) => {
          const count = this.countAppearance(t.timestamps);
          return {
            id: t.id,
            label: t.name + ': ' + count,
            value: count,
            color: {
              background: '#ffffff',
              border: t.color,
              highlight: t.color
            }
          };
        }).filter((t) => t.value >= this.min_node)
      );

      // build all combinations of two timelines
      const node_combinations = clusterTimelines.flatMap((v, i) =>
        clusterTimelines.slice(i + 1).map((w) => [v, w])
      );
      const edges = new DataSet(
        node_combinations.map((c) => {
          const overlap = this.calcTimelineOverlap(
            c[0].timestamps,
            c[1].timestamps,
          )
          return {
            from: c[0].id,
            to: c[1].id,
            id: c[0].id + c[1].id,
            label: String(overlap),
            value: overlap,
            color: {
              color: this.blendColors(c[0].color, c[1].color)
            }
          };
        }).filter((nc) => nc.value >= this.min_edge)
      );

      return { nodes: nodes, edges: edges };
    },
    blendColors(colorA, colorB) {
      const [rA, gA, bA] = colorA.match(/\w\w/g).map((c) => parseInt(c, 16));
      const [rB, gB, bB] = colorB.match(/\w\w/g).map((c) => parseInt(c, 16));
      const r = Math.round(rA + (rB - rA) * 0.5).toString(16).padStart(2, '0');
      const g = Math.round(gA + (gB - gA) * 0.5).toString(16).padStart(2, '0');
      const b = Math.round(bA + (bB - bA) * 0.5).toString(16).padStart(2, '0');
      return '#' + r + g + b;
    }
  },
  computed: {
    timelines() {
      return this.timelineStore
        .all
        .filter((timeline) => timeline.type === "PLUGIN_RESULT" && timeline.plugin && timeline.plugin.type === 'SCALAR');
    },
    visibleTimelines() {
      return Object.values(this.timelineSettings).filter((t) => t.visible);
    },
    latestFaceClustering() {
      return this.clusterTimelineItemStore.latestFaceClustering();
    },
    latestPlaceClustering() {
      return this.clusterTimelineItemStore.latestPlaceClustering();
    },
    ...mapStores(useTimelineStore, useShotStore, useClusterTimelineItemStore),
  },
  watch: {
    timelines() {
      this.updateTimelineSettings();
    },
    latestFaceClustering() {
      this.updateClusterSettings(this.latestFaceClustering, 'Face Clustering');
    },
    latestPlaceClustering() {
      this.updateClusterSettings(this.latestPlaceClustering, 'Place Clustering');
    }
  },
};
</script>
<style>
.shot-aggregation-switch label {
  padding-left: 10px;
  padding-top: 4px;
}
</style>