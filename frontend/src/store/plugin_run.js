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

export const usePluginRunStore = defineStore("pluginRun", {
  state: () => {
    return {
      pluginRuns: {},
      pluginRunList: [],
      isLoading: false,
      pluginInProgress: false,
    };
  },
  getters: {
    all: (state) => {
      return state.pluginRunList.map((id) => state.pluginRuns[id]);
    },
    forVideo: (state) => {
      return (videoId) => {
        return state.pluginRunList
          .map((id) => state.pluginRuns[id])
          .filter((e) => e.video_id === videoId);
      };
    }
  },
  actions: {
    async submit({ plugin, parameters = [], videoId = null }) {
      const formData = new FormData();
      formData.append("plugin", plugin);
      let jsonParameters = []
      parameters.forEach((p) => {
        if ("file" in p) {
          formData.append(`file_${p.name}`, p.file);
        }
        else {
          jsonParameters.push(p);
        }
      })
      formData.append("parameters", JSON.stringify(jsonParameters));

      //use video id or take it from the current video
      let video_id = videoId;
      if (videoId) {
        video_id = videoId;
      } else {
        const playerStore = usePlayerStore();
        const video = playerStore.videoId;
        if (video) {
          video_id = video;
        }
      }
      formData.append("video_id", video_id);

      return axios
        .post(`${config.API_LOCATION}/plugin/run/new`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
        .then((res) => {
          if (res.data.status === "ok") {
            this.pluginInProgress = true;
            // commit('update', res.data.entries);
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
      // .catch((error) => {
      //   const info = { date: Date(), error, origin: 'collection' };
      //   commit('error/update', info, { root: true });
      // });
    },
    async fetchAll({ addResults = false }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = { add_results: addResults };
      return axios
        .get(`${config.API_LOCATION}/plugin/run/list`, { params })
        .then((res) => {
          if (res.data.status === "ok") {
            this.updateAll(res.data.entries);
            this.pluginInProgress = this.all.filter((e) => e.status === "RUNNING" || e.status === "QUEUED").length > 0;
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async fetchForVideo({ videoId = null, fetchResults = false }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {};
      if (videoId) {
        params.video_id = videoId;
      } else {
        const playerStore = usePlayerStore();
        const videoId = playerStore.videoId;
        if (videoId) {
          params.video_id = videoId;
        }
      }
      // get the current status of all plugins
      let currentPluginRunStatus = null;
      if (videoId) {
        currentPluginRunStatus = this.forVideo(videoId);
      }
      else {
        currentPluginRunStatus = this.all;
      }
      currentPluginRunStatus = currentPluginRunStatus.map((e) => { return { id: e.id, status: e.status } })
      this.pluginInProgress = currentPluginRunStatus.filter((e) => e.status === "RUNNING" || e.status === "QUEUED").length > 0;

      return axios
        .get(`${config.API_LOCATION}/plugin/run/list`, { params })
        .then((res) => {
          if (res.data.status === "ok") {
            this.updateAll(res.data.entries);
            let newPluginRunStatus = null;
            if (videoId) {
              newPluginRunStatus = this.forVideo(videoId)
            }
            else {
              newPluginRunStatus = this.all
            }
            newPluginRunStatus = newPluginRunStatus.map((e) => { return { id: e.id, status: e.status } })
            const diff = newPluginRunStatus.map(t1 => {
              const f = currentPluginRunStatus.find(t2 => t2.id === t1.id);
              return { ...t1, oldStatus: f ? f.status : "UNKNOW" }
            })

            // generate result dict
            const result = {
              allDone: diff.filter((e) => {
                {
                  return e.status === "DONE" || e.status === "ERROR" || e.status === "UNKNOWN";
                }
              }).length == diff.length,
              newDone: diff.filter((e) => {
                {
                  return e.status === "DONE" && e.oldStatus !== "DONE";
                }
              }).map((e) => { return e.id }),
            }
            // check if all plugins are done
            this.pluginInProgress = !result.allDone;

            // get the results from the plugin
            if (fetchResults) {
              const pluginRunResultStore = usePluginRunResultStore();
              const annotationCategoryStore = useAnnotationCategoryStore();
              const annotationStore = useAnnotationStore();
              const timelineStore = useTimelineStore();
              const timelineSegmentStore = useTimelineSegmentStore();
              const timelineSegmentAnnotationStore =
                useTimelineSegmentAnnotationStore();
              const clusterTimelineItemStore = useClusterTimelineItemStore();
              // start fetching new plugin run results
              result.newDone.forEach((e) => {
                let promises = [];
                promises.push(pluginRunResultStore.fetchForVideo({ pluginRunId: e.id }));
                promises.push(annotationCategoryStore.clearStore());
                promises.push(annotationStore.clearStore());
                promises.push(annotationCategoryStore.fetchForVideo({ videoId }));
                promises.push(annotationStore.fetchForVideo({ videoId }));

                promises.push(timelineSegmentStore.fetchForVideo({ videoId }));
                promises.push(timelineSegmentAnnotationStore.fetchForVideo({ videoId }));
                promises.push(clusterTimelineItemStore.fetchAll(videoId));
                Promise.all(promises).then(
                  () => {
                    timelineStore.fetchForVideo({ videoId })
                  }
                )
              })
            }


            return result
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    clearStore() {
      this.pluginRuns = {};
      this.pluginRunList = [];
    },
    delete(id_list) {
      id_list.forEach((id) => {
          let index = this.pluginRunList.findIndex((item) => item === id);
          this.pluginRunList.splice(index, 1);
          delete this.pluginRuns[id];
        }
      )
    },
    updateAll(pluginRuns) {
      pluginRuns.forEach((e) => {
        if (e.id in this.pluginRuns) {
          const curr_plugin = this.pluginRuns[e.id];
          if (e.status !== curr_plugin.status || e.progress !== curr_plugin.progress || e.update_date !== curr_plugin.update_date) {
            const newPluginRuns = { ...this.pluginRuns };
            newPluginRuns[e.id] = e;
            Vue.set(this, "pluginRuns", newPluginRuns);
          }
          return;
        }

        this.pluginRuns[e.id] = e;
        this.pluginRunList.push(e.id);
      });
    }
  },
});
