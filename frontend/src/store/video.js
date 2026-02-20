import Vue from "vue";
import axios from "../plugins/axios";
import config from "../../app.config";

import { defineStore } from "pinia";
import { usePlayerStore } from "./player";
import { useAnnotationStore } from "./annotation";
import { useShortcutStore } from "./shortcut";
import { useAnnotationShortcutStore } from "./annotation_shortcut";
import { useAnnotationCategoryStore } from "./annotation_category";
import { useTimelineStore } from "./timeline";
import { useTimelineSegmentStore } from "./timeline_segment";
import { useTimelineSegmentAnnotationStore } from "./timeline_segment_annotation";

import { usePluginRunStore } from "./plugin_run";
import { usePluginRunResultStore } from "./plugin_run_result";
import { useClusterTimelineItemStore } from "./cluster_timeline_item";

import { useShotStore } from "./shot";

// useStore could be anything like useUser, useCart
// the first argument is a unique id of the store across your application
export const useVideoStore = defineStore("video", {
  // other options...
  state: () => {
    return {
      videos: {},
      videoList: [],
      isLoading: false,
    };
  },
  getters: {
    all(state) {
      return state.videoList.map((id) => state.videos[id]);
    },
    get(state) {
      return (id) => {
        return state.videos[id];
      };
    },
  },
  actions: {
    async fetch({
      videoId,
      includeTimeline = true,
      includeAnnotation = true,
      includeAnalyser = true,
      includeShortcut = true,
      includeClusterTimelineItem = true,
      addResults = true,
    }) {
      this.isLoading = true;
      let promises = [];
      const playerStore = usePlayerStore();
      const annotationCategoryStore = useAnnotationCategoryStore();
      const annotationStore = useAnnotationStore();
      const timelineStore = useTimelineStore();
      const timelineSegmentStore = useTimelineSegmentStore();
      const timelineSegmentAnnotationStore =
        useTimelineSegmentAnnotationStore();
      const pluginRunStore = usePluginRunStore();
      const pluginRunResultStore = usePluginRunResultStore();
      const shortcutStore = useShortcutStore();
      const annotationShortcutStore = useAnnotationShortcutStore();
      const clusterTimelineItemStore = useClusterTimelineItemStore();

      const shotStore = useShotStore();

      playerStore.clearStore();
      promises.push(playerStore.fetchVideo({ videoId }));
      promises.push(shotStore.fetchForVideo({ videoId }));
      if (includeAnnotation) {
        annotationCategoryStore.clearStore();
        annotationStore.clearStore();
        promises.push(annotationCategoryStore.fetchForVideo({ videoId }));
        promises.push(annotationStore.fetchForVideo({ videoId }));
      }
      if (includeTimeline) {
        promises.push(
          timelineStore
            .fetchForVideo({ videoId })
            .then(() => {
              return timelineSegmentStore.fetchForVideo({ videoId });
            })
            .then(() => {
              return timelineSegmentAnnotationStore.fetchForVideo({ videoId });
            }),
        );
      }
      if (includeAnalyser) {
        pluginRunStore.clearStore();
        pluginRunResultStore.clearStore();
        promises.push(
          pluginRunStore.fetchForVideo({
            videoId: videoId,
            addResults: addResults,
          }),
        );
        promises.push(
          pluginRunResultStore.fetchForVideo({
            videoId: videoId,
            addResults: addResults,
          }),
        );
      }
      if (includeShortcut) {
        shortcutStore.clearStore();
        annotationShortcutStore.clearStore();
        promises.push(shortcutStore.fetchForVideo({ videoId }));
        promises.push(annotationShortcutStore.fetchForVideo({ videoId }));
      }
      if (includeClusterTimelineItem) {
        clusterTimelineItemStore.clearStore();
        promises.push(clusterTimelineItemStore.fetchAll(videoId));
      }
      return Promise.all(promises).finally(() => {
        console.log("Loading done!");
        this.isLoading = false;
      });
    },
    async fetchAll() {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      return axios
        .get(`${config.API_LOCATION}/video/list`)
        .then((res) => {
          if (res.data.status === "ok") {
            this.replaceStore(res.data.entries);
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async rename({ videoId, name }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        id: videoId,
        name: name,
      };

      const newVideos = { ...this.videos };
      newVideos[videoId].name = name;
      Vue.set(this, "videos", newVideos);

      return axios
        .post(`${config.API_LOCATION}/video/rename`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            // commit("rename", { videoId, name });
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
      // .catch((error) => {
      //     const info = { date: Date(), error, origin: 'collection' };
      //     commit('error/update', info, { root: true });
      // });
    },
    async delete(video_id) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      const params = {
        id: video_id,
      };
      return axios
        .post(`${config.API_LOCATION}/video/delete`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            this.deleteFromStore([video_id]);
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
      // .catch((error) => {
      //     const info = { date: Date(), error, origin: "collection" };
      //     commit("error/update", info, { root: true });
      // });
    },
    async export({ format, parameters = [], videoId = null }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      const formData = new FormData();
      formData.append("format", format);
      let jsonParameters = [];
      // formData.append("parameters", JSON.stringify(parameters));
      parameters.forEach((p) => {
        if ("file" in p) {
          formData.append(`file_${p.name}`, p.file);
        } else {
          jsonParameters.push(p);
        }
      });
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
      console.log(formData);
      return axios
        .post(`${config.API_LOCATION}/video/export`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
        .then((res) => {
          console.log("data");
          console.log(res.data);
          if (res.data.status === "ok") {
            if (res.data.extension === "zip") {
              const filecontent = Buffer.from(res.data.file, "base64");
              let blob = new Blob([filecontent], { type: `application/zip` });
              let link = document.createElement("a");
              link.href = window.URL.createObjectURL(blob);
              link.download = `${res.data.video_name}.${res.data.extension}`;
              link.click();
            } else if (
              res.data.extension === "csv" ||
              res.data.extension === "eaf"
            ) {
              let blob = new Blob([res.data.file], {
                type: `text/${res.data.extension}`,
              });
              let link = document.createElement("a");
              link.href = window.URL.createObjectURL(blob);
              link.download = `${res.data.video_name}.${res.data.extension}`;
              link.click();
            }
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
    // async exportJson(videoId = null) {
    //     if (this.isLoading) {
    //         return
    //     }
    //     this.isLoading = true

    //     let params = {};
    //     //use video id or take it from the current video

    //     if (videoId) {
    //         params.video_id = videoId;
    //     } else {

    //         const playerStore = usePlayerStore();
    //         const currentVideoId = playerStore.videoId;
    //         if (currentVideoId) {
    //             params.video_id = currentVideoId;
    //         }
    //     }
    //     return axios
    //         .get(`${config.API_LOCATION}/video/export/json`, { params })
    //         .then((res) => {
    //             if (res.data.status === "ok") {
    //                 let blob = new Blob([res.data.file], { type: "text/json" });
    //                 let link = document.createElement("a");
    //                 link.href = window.URL.createObjectURL(blob);
    //                 link.download = `${params.video_id}.json`;
    //                 link.click();
    //             }
    //         })
    //         .finally(() => {
    //             this.isLoading = false;
    //         });
    //     // .catch((error) => {
    //     //   const info = { date: Date(), error, origin: 'collection' };
    //     //   commit('error/update', info, { root: true });
    //     // });
    // },
    clearStore() {
      this.videos = {};
      this.videoList = [];
    },
    deleteFromStore(ids) {
      ids.forEach((id) => {
        let index = this.videoList.findIndex((f) => f === id);
        this.videoList.splice(index, 1);
        delete this.videos[id];
      });
    },
    addToStore(video) {
      this.videos[video.id] = video;
      this.videoList.push(video.id);
    },
    replaceStore(videos) {
      this.videos = {};
      this.videoList = [];
      videos.forEach((e) => {
        this.videos[e.id] = e;
        this.videoList.push(e.id);
      });
    },
  },
});
