import Vue from "vue";
import axios from "../plugins/axios";
import config from "../../app.config";
import { defineStore } from "pinia";
import { usePlayerStore } from "@/store/player";
import { usePluginRunResultStore } from "@/store/plugin_run_result";
import { useAnnotationStore } from "./annotation";
import { useAnnotationCategoryStore } from "./annotation_category";
import { useTimelineStore } from "./timeline";
import { useTimelineSegmentStore } from "./timeline_segment";
import { useTimelineSegmentAnnotationStore } from "./timeline_segment_annotation";
import { useClusterTimelineItemStore } from "./cluster_timeline_item";

export const usePluginStore = defineStore("plugin", {
  state: () => {
    return {
      plugins: {},
      pluginList: [],
      isLoading: false,
    };
  },
  getters: {
    all: (state) => {
      return state.pluginList.map((id) => state.plugins[id]);
    },
  },
  actions: {
    async fetchAll() {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = { };
      return axios
        .get(`${config.API_LOCATION}/plugin/list`, { params })
        .then((res) => {
          if (res.data.status === "ok") {
            this.updateAll(res.data.entries);
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    clearStore() {
      this.plugins = {};
      this.pluginList = [];
    },
    updateAll(plugins) {
      plugins.forEach((e) => {
        this.plugins[e.name] = e;
        this.pluginList.push(e.name);
      });
    }
  },
});
