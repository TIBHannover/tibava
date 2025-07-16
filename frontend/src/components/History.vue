<template>
  <v-dialog v-model="menu" offset-y bottom left width="700px">
    <template v-slot:activator="{ attrs, on: menu }">
      <v-btn
        tile
        text
        v-bind="attrs"
        v-on="menu"
        :title="$t('plugin.menu.title')"
      >
        <v-icon color="primary">mdi-history</v-icon>
        <v-badge
          v-if="numRunningPlugins > 0"
          color="accent"
          :content="numRunningPlugins"
        >
          History
        </v-badge>
        <span v-else> History </span>
      </v-btn>
    </template>
    <v-data-table
      :items-per-page="10"
      :headers="headers"
      :items="pluginRuns"
      item-key="id"
      class="elevation-1"
    >
      <template v-slot:item.status="{ value }">
        <v-chip :color="progressColor(value)"> {{ value }}</v-chip>
      </template>
      <template v-slot:item.progress="{ value }">
        <v-progress-linear :value="value * 100" height="8"> </v-progress-linear>
      </template>
    </v-data-table>
  </v-dialog>
</template>

<script>
import ModalPlugin from "@/components/ModalPlugin.vue";

import { mapStores } from "pinia";
import { usePlayerStore } from "@/store/player";
import { usePluginRunStore } from "@/store/plugin_run";
import { usePluginRunResultStore } from "@/store/plugin_run_result";

export default {
  data() {
    return {
      menu: false,
      showModalPlugin: false,
      headers: [
        {
          text: "Plugin Name",
          align: "start",
          sortable: false,
          value: "type",
        },
        { text: "Date", value: "date" },
        { text: "Progress", value: "progress" },
        { text: "Status", value: "status" },
      ],
    };
  },
  methods: {
    progressColor(status) {
      if (status === "ERROR") {
        return "red";
      }
      if (status === "RUNNING") {
        return "blue";
      }
      if (status === "DONE") {
        return "green";
      }
      return "yellow";
    },
    indeterminate(status) {
      if (status === "QUEUED") {
        return true;
      }
      if (status === "WAITING") {
        return true;
      }
      return false;
    },
    pluginStatus(status) {
      if (status === "UNKNOWN") {
        return this.$t("modal.plugin.status.unknown");
      }
      if (status === "ERROR") {
        return this.$t("modal.plugin.status.error");
      }
      if (status === "DONE") {
        return this.$t("modal.plugin.status.done");
      }
      if (status === "RUNNING") {
        return this.$t("modal.plugin.status.running");
      }
      if (status === "QUEUED") {
        return this.$t("modal.plugin.status.queued");
      }
      if (status === "WAITING") {
        return this.$t("modal.plugin.status.waiting");
      }
      return status;
    },
    pluginName(type) {
      if (type === "aggregate_scalar") {
        return this.$t("modal.plugin.aggregation.plugin_name");
      }
      if (type === "audio_amp") {
        return this.$t("modal.plugin.audio_waveform.plugin_name");
      }
      if (type === "audio_freq") {
        return this.$t("modal.plugin.audio_frequency.plugin_name");
      }
      if (type === "audio_rms") {
        return this.$t("modal.plugin.audio_rms.plugin_name");
      }
      if (type === "clip") {
        return this.$t("modal.plugin.clip.plugin_name");
      }
      if (type === "x_clip") {
        return this.$t("modal.plugin.x_clip.plugin_name");
      }
      if (type === "clip_ontology") {
        return this.$t("modal.plugin.clip_ontology.plugin_name");
      }
      if (type === "color_analysis") {
        return this.$t("modal.plugin.color_analysis.plugin_name");
      }
      if (type === "color_brightness_analysis") {
        return this.$t("modal.plugin.color_brightness_analysis.plugin_name");
      }
      if (type === "facedetection") {
        return this.$t("modal.plugin.facedetection.plugin_name");
      }
      if (type === "face_clustering") {
        return this.$t("modal.plugin.face_clustering.plugin_name");
      }
      if (type === "deepface_emotion") {
        return this.$t("modal.plugin.faceemotion.plugin_name");
      }
      if (type === "insightface_facesize") {
        return this.$t("modal.plugin.facesize.plugin_name");
      }
      if (type === "insightface_identification") {
        return this.$t("modal.plugin.face_identification.plugin_name");
      }
      if (type === "blip_vqa") {
        return this.$t("modal.plugin.blip.plugin_name");
      }
      if (type === "place_identification") {
        return this.$t("modal.plugin.place_identification.plugin_name");
      }
      if (type === "places_classification") {
        return this.$t("modal.plugin.places_classification.plugin_name");
      }
      if (type === "place_clustering") {
        return this.$t("modal.plugin.place_clustering.plugin_name");
      }
      if (type === "whisper") {
        return this.$t("modal.plugin.whisper.plugin_name");
      }
      if (type === "shotdetection") {
        return this.$t("modal.plugin.shot_detection.plugin_name");
      }
      if (type === "shot_density") {
        return this.$t("modal.plugin.shot_density.plugin_name");
      }
      if (type === "shot_scalar_annotation") {
        return this.$t("modal.plugin.shot_scalar_annotation.plugin_name");
      }
      if (type === "shot_type_classification") {
        return this.$t("modal.plugin.shot_type_classification.plugin_name");
      }
      if (type === "thumbnail") {
        return this.$t("modal.plugin.thumbnail.plugin_name");
      }
      return type;
    },
  },
  computed: {
    pluginRuns() {
      const pluginRuns = this.pluginRunStore
        .forVideo(this.playerStore.videoId)
        .sort((a, b) => {
          return new Date(b.date) - new Date(a.date);
        })
        .map((pluginRun, index) => {
          return {
            id: index,
            type: this.pluginName(pluginRun.type),
            date: pluginRun.date
              .replace("T", " ")
              .replace("Z", "")
              .substring(0, pluginRun.date.length - 5),
            progress: parseFloat(pluginRun.progress), // * 100 + "%",
            status: pluginRun.status,
          };
        });
      return pluginRuns;
    },
    numRunningPlugins() {
      return this.pluginRuns.filter((e) => {
        return e.status !== "DONE" && e.status !== "ERROR";
      }).length;
    },

    ...mapStores(usePlayerStore, usePluginRunStore, usePluginRunResultStore),
  },
  components: {
    ModalPlugin,
  },
};
</script>

<style>
.v-menu__content .v-btn:not(.accent) {
  text-transform: capitalize;
  justify-content: left;
}

.v-btn:not(.v-btn--round).v-size--large {
  height: 48px;
}

.plugin-overview {
  background-color: rgb(255, 255, 255) !important;
  max-height: 500px;
  padding: 0;
  margin: 0;
}

.v-list-item__content.plugin-overview {
  min-width: 350px;
  max-width: 500px;
  letter-spacing: 0.0892857143em;
  overflow: auto;
  /* border-bottom: 1px solid #f5f5f5; */
}

.text-overflow {
  overflow: hidden;
  white-space: nowrap;
  /* Don't forget this one */
  text-overflow: ellipsis;
}

.plugin-name {
  font-weight: bold;
}

.v-menu__content .plugin-overview .v-btn:not(.accent) {
  justify-content: center;
}

.v-data-table .v-data-table-header tr th {
  font-size: 20px !important;
}
</style>
