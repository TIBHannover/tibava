<template>
  <v-dialog v-model="show" max-width="1000">
    <template v-slot:activator="{ on }">
      <v-btn v-on="on" text block large>
        <v-icon left>{{ "mdi-chart-line-variant" }}</v-icon>
        {{ $t("modal.timeline.visualization.link") }}
      </v-btn>
    </template>
    <v-card>
      <v-card-title class="mb-2">
        {{ $t("modal.timeline.visualization.title") }}

        <v-btn icon @click.native="show = false" absolute top right>
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-col cols="12">
          <v-row>
            <v-btn-toggle v-model="visualization_idx" borderless>
              <v-btn
                class="mr-4"
                v-for="visualization_option in visualization_options"
                :key="visualization_option.label"
              >
                {{ visualization_option.label }}
              </v-btn>
            </v-btn-toggle>
          </v-row>
          <v-row>
            <v-list class="color-map-list">
              <v-subheader>
                {{ $t("modal.timeline.visualization.description") }}
              </v-subheader>
              <v-list-item-group v-model="colormap_idx" color="primary">
                <template v-for="(colormap, i) in colormap_options">
                  <v-list-item :key="colormap.id">
                    <div
                      class="color-map"
                      :style="{
                        background: colormapBackground(colormap.value),
                      }"
                    ></div>
                  </v-list-item>
                  <v-divider
                    :key="i"
                    v-if="i < colormap_options.length - 1"
                  ></v-divider>
                </template>
              </v-list-item-group>
            </v-list>
          </v-row>
          <v-row>
            <v-checkbox v-model="colormap_inverse" :label="$t('modal.timeline.visualization.colormap_inverse')"></v-checkbox>
          </v-row>
        </v-col>
      </v-card-text>
      <v-card-actions class="pt-0">
        <v-btn class="mr-4" @click="submit" :disabled="isSubmitting">
          {{ $t("modal.timeline.visualization.update") }}
        </v-btn>
        <v-btn @click="show = false">{{
          $t("modal.timeline.visualization.close")
        }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapStores } from "pinia";
import { useTimelineStore } from "@/store/timeline";
import { usePluginRunResultStore } from "@/store/plugin_run_result";
import { scalarToString } from "@/plugins/draw/utils";

export default {
  props: ["timeline"],
  data() {
    return {
      show: false,
      isSubmitting: false,
      visualization_idx: null,
      visualization_proxy: null,
      visualization_options: [],
      items: [],
      colormap_inverse_proxy: null,
      colormap_idx: null,
      colormap_proxy: null,
      colormap_options: [],
      colormap_default: "TIBReds",
    };
  },
  computed: {
    timeline_type() {
      const timeline = this.timelineStore.get(this.timeline);

      if (
        timeline.type == "PLUGIN_RESULT" &&
        "plugin_run_result_id" in timeline
      ) {
        const result = this.pluginRunResultStore.get(
          timeline.plugin_run_result_id
        );
        if (result) {
          timeline.plugin = { data: result.data, type: result.type };
        }
      }
      return timeline.plugin.type;
    },
    visualization: {
      get() {
        const timeline = this.timelineStore.get(this.timeline);
        return this.visualization_proxy === null
          ? timeline.visualization
          : this.visualization_proxy;
      },
      set(val) {
        this.visualization_proxy = val;
      },
    },
    colormap_inverse: {
      get() {
        const timeline = this.timelineStore.get(this.timeline);
        return this.colormap_inverse_proxy === null
          ? timeline.colormap_inverse
          : this.colormap_inverse_proxy;
      },
      set(val) {
        this.colormap_inverse_proxy = val;
      },
    },
    colormap: {
      get() {
        const timeline = this.timelineStore.get(this.timeline);
        return this.colormap_proxy === null
          ? timeline.colormap
          : this.colormap_proxy;
      },
      set(val) {
        this.colormap_proxy = val;
      },
    },
    ...mapStores(useTimelineStore, usePluginRunResultStore),
  },
  methods: {
    async submit() {
      if (this.isSubmitting) {
        return;
      }
      this.isSubmitting = true;

      let visualization = this.visualization;
      if (this.visualization_idx !== null) {
        visualization =
          this.visualization_options[this.visualization_idx].value;
      }
      let colormap = null;
      if (this.colormap_idx === null) {
        colormap = this.colormap_default;
      } else {
        colormap = this.colormap_options[this.colormap_idx].value;
      }

      await this.timelineStore.changeVisualization({
        timelineId: this.timeline,
        visualization: visualization,
        colormap: colormap,
        colormap_inverse: this.colormap_inverse
      });

      this.isSubmitting = false;
      this.show = false;
    },
    colormapBackground(colormapName) {
      const colorStops = Array.from(Array(10).keys())
        .map((k) => k / 10)
        .map((k) => `${scalarToString(k, this.colormap_inverse, colormapName)} ${k * 100}%`)
        .join(",");
      const cssString = `linear-gradient(90deg, ${colorStops})`;
      return cssString;
    },
  },
  watch: {
    show(value) {
      if (value) {
        this.nameProxy = null;

        if (this.timeline_type == "SCALAR") {
          this.visualization_options = [
            { label: "Line Chart", value: "SCALAR_LINE" },
            { label: "Color Chart", value: "SCALAR_COLOR" },
          ];

          var visualization_lut = { SCALAR_LINE: 0, SCALAR_COLOR: 1 };
          // TODO other data types

          // preselect button with current visualization option
          if (this.visualization in visualization_lut) {
            this.visualization_idx = visualization_lut[this.visualization];
          }
        }

        if (this.timeline_type === "SCALAR" || this.timeline_type === "HIST") {
          this.colormap_options = [
            { value: "RdYlBu" },
            { value: "RdYlGn" },
            { value: "Blues" },
            { value: "Greens" },
            { value: "Reds" },
            { value: "TIBReds" },
            { value: "Greys" },
            { value: "YlGnBu" },
            { value: "Viridis" },
            { value: "Plasma" },
            { value: "YlOrRd" },
          ];

          var colormap_lut = {
            RdYlBu: 0,
            RdYlGn: 1,
            Blues: 2,
            Greens: 3,
            Reds: 4,
            TIBReds: 5,
            Greys: 6,
            YlGnBu: 7,
            Viridis: 8,
            Plasma: 9,
            YlOrRd: 10,
          };

          // preselect button with current visualization option
          if (this.colormap in colormap_lut) {
            if (this.colormap) {
              this.colormap_idx = colormap_lut[this.colormap];
            } else {
              this.colormap_idx = 0;
            }
          }
        }

        this.$emit("close");
      }
    },
  },
};
</script>

<style scoped>
.color-map {
  width: 100%;
  height: 100%;
  min-width: 200px;
  min-height: 30px;
  border: 1px;
  border-color: gray;
  border-style: solid;
}

.color-map-list {
  width: 100%;
}
</style>



