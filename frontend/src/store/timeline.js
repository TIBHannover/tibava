import Vue from "vue";
import axios from "../plugins/axios";
import config from "../../app.config";
import { defineStore } from "pinia";
import { useTimelineSegmentAnnotationStore } from "@/store/timeline_segment_annotation";
import { useTimelineSegmentStore } from "@/store/timeline_segment";
import { usePlayerStore } from "@/store/player";
import { usePluginRunResultStore } from "@/store/plugin_run_result";

export const useTimelineStore = defineStore("timeline", {
  state: () => {
    return {
      timelines: {},
      timelineList: [],
      timelineListSelected: [],
      timelineListAdded: [],
      timelineListDeleted: [],
      timelineListChanged: [],
      timelineSelectedTimeRange: {
        start: null,
        end: null,
      },
      visualizationData: null,
      isLoading: false,
    };
  },
  getters: {
    getVisualizationData(state) {
      return state.visualizationData;
    },
    selectedTimeRangeStart(state) {
      if (
        state.timelineSelectedTimeRange.start === null ||
        state.timelineSelectedTimeRange.end === null
      ) {
        return null;
      }
      return Math.min(
        state.timelineSelectedTimeRange.start,
        state.timelineSelectedTimeRange.end
      );
    },
    selectedTimeRangeEnd(state) {
      if (
        state.timelineSelectedTimeRange.start === null ||
        state.timelineSelectedTimeRange.end === null
      ) {
        return null;
      }
      return Math.max(
        state.timelineSelectedTimeRange.start,
        state.timelineSelectedTimeRange.end
      );
    },
    forVideo(state) {
      return (videoId) => {
        return state.timelineList
          .map((id) => state.timelines[id])
          .filter((e) => e.video_id === videoId);
      };
    },
    all(state) {
      return Object.values(state.timelines);
    },
    added(state) {
      return state.timelineListAdded.map((data) => [
        data[0],
        state.timelines[data[1]],
      ]);
    },
    deleted(state) {
      return state.timelineListDeleted;
    },
    changed(state) {
      return state.timelineListChanged.map((data) => [
        data[0],
        state.timelines[data[1]],
      ]);
    },
    get(state) {
      return (id) => {
        return state.timelines[id];
      };
    },
    getLatest(state) {
      return () => {
        const id = state.timelineListAdded.at(-1)[1];
        return state.timelines[id];
      }
    },
    segmentPosition(state) {
      return (segmentId) => {
        let result = null;
        state.timelineList
          .map((id) => state.timelines[id])
          .forEach((timeline, timelinePos) => {
            if (timeline.segments != null) {
              timeline.segments.forEach((segment, segmentPos) => {
                if (segment.id === segmentId) {
                  result = { timeline: timelinePos, segment: segmentPos };
                }
              });
            }
          });
        return result;
      };
    },
    getSegmentByPosition(state) {
      return (timelinePos, segmentPos) => {
        let result = null;
        state.timelineList
          .map((id) => state.timelines[id])
          .forEach((timeline, iTimelinePos) => {
            if (timeline.segments != null && timelinePos === iTimelinePos) {
              timeline.segments.forEach((segment, iSegmentPos) => {
                if (iSegmentPos === segmentPos) {
                  result = segment.id;
                }
              });
            }
          });
        return result;
      };
    },

    selected(state) {
      return state.timelineListSelected.map((id) => state.timelines[id]);
    },
    lastSelected(state) {
      if (state.timelineListSelected.length <= 0) {
        return null;
      }
      return state.timelineListSelected.map((id) => state.timelines[id])[
        state.timelineListSelected.length - 1
      ];
    },
    getPrevious(state) {
      return (id) => {
        if (!id) {
          return this.all.sort((a, b) => a.order - b.order)[0];
        }
        const timeline = state.timelines[id];
        const timelines = this.all
          .sort((a, b) => a.order - b.order)
          .filter((e) => e.order < timeline.order);
        if (timelines.length <= 0) {
          return null;
        }
        return timelines[timelines.length - 1];
      };
    },
    getNext(state) {
      return (id) => {
        if (!id) {
          return this.all.sort((a, b) => a.order - b.order)[0];
        }
        const timeline = state.timelines[id];
        const timelines = this.all
          .sort((a, b) => a.order - b.order)
          .filter((e) => e.order > timeline.order);
        if (timelines.length <= 0) {
          return null;
        }
        return timelines[0];
      };
    },
  },
  actions: {
    setVisualizationData(data) {
      this.visualizationData = data;
    },
    setSelectedTimeRangeStart(time) {
      this.timelineSelectedTimeRange.start = time;
    },
    setSelectedTimeRangeEnd(time) {
      this.timelineSelectedTimeRange.end = time;
    },
    clearSelection() {
      this.timelineListSelected = [];
      // this.timelineListSelected.start = null
      // this.timelineListSelected.end = null
      // this.timelineSegmentList.forEach((id) => {
      //     this.timelineSegments[id].selected = false;
      // })
    },
    addToSelection(timelineId) {
      this.timelineListSelected.push(timelineId);
      // if (timelineId in this.timelineSegments) {
      //     this.timelineSegments[timelineId].selected = true;
      // }
    },
    removeFromSelection(timelineId) {
      let segment_index = this.timelineListSelected.findIndex(
        (f) => f === timelineId
      );
      this.timelineListSelected.splice(segment_index, 1);

      // if (timelineSegmentId in this.timelineSegments) {
      //     this.timelineSegments[timelineSegmentId].selected = false;
      // }
    },
    async fetchAll({ addResultsType = false }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;
      let params = { add_results_type: addResultsType };

      return axios
        .get(`${config.API_LOCATION}/timeline/list_all`, { params })
        .then((res) => {
          if (res.data.status === "ok") {
            this.updateStore(res.data.entries);
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async fetchForVideo({ videoId = null, clear = true }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      //use video id or take it from the current video
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
      if (clear) {
        this.clearStore();
      }
      return axios
        .get(`${config.API_LOCATION}/timeline/list`, { params })
        .then((res) => {
          if (res.data.status === "ok") {
            this.updateStore(res.data.entries);
            // load plugin_run_results into timeline objects
            const pluginRunResultStore = usePluginRunResultStore();
            res.data.entries.forEach((timeline) => {
              if (!('plugin' in timeline) && timeline.type == "PLUGIN_RESULT" && "plugin_run_result_id" in timeline) {
                const result = pluginRunResultStore.get(timeline.plugin_run_result_id);
                if (result) {
                  timeline.plugin = { data: result.data, type: result.type };
                }
              }
            });
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
    async duplicate({ id, name = null, includeannotations = true }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        id: id,
        name: name,
        include_annotations: includeannotations,
      };

      return axios
        .post(`${config.API_LOCATION}/timeline/duplicate`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            // add annotations
            const timelineSegmentAnnotationStore =
              useTimelineSegmentAnnotationStore();
            timelineSegmentAnnotationStore.addToStore(
              res.data.timeline_segment_annotation_added
            );

            // add timeline segments
            const timelineSegmentStore = useTimelineSegmentStore();
            timelineSegmentStore.addToStore(res.data.timeline_segment_added);

            // add timeline
            this.addToStore(res.data.timeline_added);

            // let timeline know that something change
            this.notifyChanges({
              timelineIds: [res.data.timeline_added.map((e) => e.id)],
            });
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
      // .catch((error) => {
      //     const info = { date: Date(), error, origin: 'upload' };
      //     commit('error/update', info, { root: true });
      // });
    },
    async create({ name, videoId = null }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        name: name,
      };

      if (videoId) {
        params.video_id = videoId;
      } else {
        const playerStore = usePlayerStore();
        const videoId = playerStore.videoId;
        if (videoId) {
          params.video_id = videoId;
        }
      }

      return axios
        .post(`${config.API_LOCATION}/timeline/create`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            this.addToStore(res.data.timeline_added);

            const timelineSegmentStore = useTimelineSegmentStore();
            timelineSegmentStore.addToStore(res.data.timeline_segment_added);
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
      // .catch((error) => {
      //     const info = { date: Date(), error, origin: 'upload' };
      //     commit('error/update', info, { root: true });
      // });
    },
    async importEAF(params) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      const formData = new FormData();

      //use video id or take it from the current video
      const playerStore = usePlayerStore();
      const videoId = playerStore.videoId;
      formData.append("file", params.importfile);
      formData.append("video_id", videoId);

      return axios
        .post(`${config.API_LOCATION}/timeline/import/eaf`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async delete(timeline_id) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        id: timeline_id,
      };

      // update own store
      this.deleteFromStore([timeline_id]);

      // update all segments
      const timelineSegmentStore = useTimelineSegmentStore();
      timelineSegmentStore.deleteTimeline(timeline_id);

      return axios
        .post(`${config.API_LOCATION}/timeline/delete`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            // commit("delete", timeline_id);
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
    async rename({ timelineId, name }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        id: timelineId,
        name: name,
      };

      const newTimelines = { ...this.timelines };
      newTimelines[timelineId].name = name;
      Vue.set(this, "timelines", newTimelines);

      return axios
        .post(`${config.API_LOCATION}/timeline/rename`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            // commit("rename", { timelineId, name });
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
    async changeVisualization({ timelineId, visualization, colormap = null, colormap_inverse = false }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        id: timelineId,
        visualization: visualization,
        colormap: colormap,
        colormap_inverse: colormap_inverse,
      };

      const newTimelines = { ...this.timelines };
      newTimelines[timelineId].visualization = visualization;
      newTimelines[timelineId].colormap = colormap;
      newTimelines[timelineId].colormap_inverse = colormap_inverse;
      Vue.set(this, "timelines", newTimelines);

      this.timelineListChanged.push([Date.now(), timelineId]);

      return axios
        .post(`${config.API_LOCATION}/timeline/changevisualization`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            // commit("changevisualization", { timelineId, visualization });
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async setParent({ timelineId, parentId }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        timelineId: timelineId,
        parentId: parentId,
      };

      if (!parentId) {
        params.parentId = null;
      }

      const newTimelines = { ...this.timelines };
      newTimelines[timelineId].parent_id = parentId;
      Vue.set(this, "timelines", newTimelines);

      return axios
        .post(`${config.API_LOCATION}/timeline/setparent`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            // commit("setParent", { timelineId, parentId });
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async setCollapse({ timelineId, collapse }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        timelineId: timelineId,
        collapse: collapse,
      };

      const newTimelines = { ...this.timelines };
      newTimelines[timelineId].collapse = collapse;
      Vue.set(this, "timelines", newTimelines);
      this.updateVisibleStore();

      return axios
        .post(`${config.API_LOCATION}/timeline/setcollapse`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            // commit("setCollapse", { timelineId, collapse });
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async setOrder({ order }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {
        order: order,
      };

      Vue.set(this, "timelineList", order);

      this.timelineList.forEach((id, i) => {
        Vue.set(this.timelines[id], 'order', i);
      });

      return axios
        .post(`${config.API_LOCATION}/timeline/setorder`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            // commit("setorder", { order });
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async notifyChanges({ timelineIds }) {
      timelineIds.forEach((id) => {
        this.timelineListChanged.push([Date.now(), id]);
      });
    },
    clearStore() {
      this.timelineListSelected = [];
      this.timelineListAdded = [];
      this.timelineListDeleted = [];
      this.timelineListChanged = [];
      Object.keys(this.timelines).forEach(key => {
        Vue.delete(this.timelines, key);
      });
      this.timelineList = [];
    },
    deleteFromStore(ids) {
      ids.forEach((id) => {
        this.timelineListDeleted.push([Date.now(), id]);
        let index = this.timelineList.findIndex((f) => f === id);
        this.timelineList.splice(index, 1);
        Vue.delete(this.timelines, id);
      });
      this.updateVisibleStore();
    },
    addToStore(timelines) {
      timelines.forEach((e) => {
        this.timelineListAdded.push([Date.now(), e.id]);
        Vue.set(this.timelines, e.id, e);
        this.timelineList.push(e.id);
      });
      this.updateVisibleStore();
    },
    updateStore(timelines) {
      timelines.forEach((e) => {
        if (e.id in this.timelines) {
          return;
        }
        this.timelineListAdded.push([Date.now(), e.id]);
        Vue.set(this.timelines, e.id, e);
        this.timelineList.push(e.id);
      });
      this.updateVisibleStore();
    },
    updateVisibleStore() {
      const that = this;
      // TODO this runs forever
      function parentCollapsed(e) {
        if (!e.parent_id) {
          return false;
        }

        let parent_id = e.parent_id;

        while (parent_id != null) {
          let parent = that.get(parent_id);
          parent_id = parent.parent_id;
          if (parent.collapse) {
            return true;
          }
        }

        return false;
      }
      this.timelineList.map((e) => {
        this.timelines[e].visible = !parentCollapsed(this.timelines[e]);
        return e;
      });
    },
  },
});
