<template>
  <v-expansion-panels>
    <v-expansion-panel @change="change">
      <v-expansion-panel-header>
        {{ $t("visualization.title") }}
      </v-expansion-panel-header>
      <v-expansion-panel-content>
        <v-tabs horizontal class="tabs-left">
          <v-tab>
            <v-icon left> mdi-chart-scatter-plot </v-icon>
            <span class="text-button">
              {{ $t("visualization.controls.plotTypes.scatterPlot") }}
            </span>
          </v-tab>
          <v-tab>
            <v-icon left> mdi-chart-line </v-icon>
            <span class="text-button">
              {{ $t("visualization.controls.plotTypes.linePlot") }}
            </span>
          </v-tab>
          <v-tab>
            <v-icon left>mdi-vector-polygon</v-icon>
            <span class="text-button">
              {{ $t("visualization.controls.plotTypes.constellationGraph") }}
            </span>
          </v-tab>
          <v-tab-item>
            <VisualizationGraph v-if="!collapsed" showLegend="true" plotType="scatter" style="height: 400px; width: calc(100vw - 120px);"></VisualizationGraph>
          </v-tab-item>
          <v-tab-item>
            <VisualizationGraph v-if="!collapsed" showLegend="true" plotType="line" style="height: 400px; width: calc(100vw - 120px);"></VisualizationGraph>
          </v-tab-item>
          <v-tab-item>
            <VisualisationConstellationGraph v-if="!collapsed"></VisualisationConstellationGraph>
          </v-tab-item>
        </v-tabs>
      </v-expansion-panel-content>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script>
import VisualisationConstellationGraph from "./VisualisationConstellationGraph.vue";
import VisualizationGraph from "./VisualizationGraph.vue";

export default {
  data() {
    return {
      collapsed: true
    };
  },
  methods: {
    change() {
      this.collapsed = !this.collapsed;
    }
  },
  components: { VisualizationGraph, VisualisationConstellationGraph }
};
</script>
