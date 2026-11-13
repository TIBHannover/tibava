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

import { usePluginStore } from "./plugin";
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
      videoSelected: [],
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
    selected(state) {
      return state.videoList.filter((id) => state.videoSelected.includes(id));
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
      const pluginStore = usePluginStore();
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
      promises.push(pluginStore.fetchAll());
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
            })
        );
      }
      if (includeAnalyser) {
        pluginRunStore.clearStore();
        pluginRunResultStore.clearStore();
        promises.push(
          pluginRunStore.fetchForVideo({
            videoId: videoId,
            addResults: addResults,
          })
        );
        promises.push(
          pluginRunResultStore.fetchForVideo({
            videoId: videoId,
            addResults: addResults,
          })
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
    async accept_terms({ videoId }) {
      console.log(videoId);
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        id: videoId,
      };

      return axios
        .post(`${config.API_LOCATION}/video/accept_terms`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            // commit("rename", { videoId, name });
            return true;
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
    clearStore() {
      this.videos = {};
      this.videoList = [];
      this.videoSelected = [];
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
      this.videoSelected = [];
      videos.forEach((e) => {
        this.videos[e.id] = e;
        this.videoList.push(e.id);
      });
    },
    toggleSelected(id) {
      if (this.videoSelected.includes(id)) {
        let index = this.videoSelected.findIndex((f) => f === id);
        this.videoSelected.splice(index, 1);
      } else {
        this.videoSelected.push(id);
      }
    },
    clearSelected() {
      this.videoSelected = [];
    },
    pushSelected(id) {
      this.videoSelected.push(id);
    },
  },
});
