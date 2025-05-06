import Vue from "vue";
import axios from "../plugins/axios";
import config from "../../app.config";
import { defineStore } from "pinia";

import { useTimelineSegmentAnnotationStore } from "@/store/timeline_segment_annotation";
import { useAnnotationCategoryStore } from "@/store/annotation_category";
import { useAnnotationStore } from "@/store/annotation";
import { useTimelineStore } from "@/store/timeline";
import { useShotStore } from "@/store/shot";
import { usePlayerStore } from "@/store/player";

export const useTimelineSegmentStore = defineStore("timelineSegment", {
  state: () => {
    return {
      timelineSegments: {},
      timelineSegmentList: [],
      timelineSegmentListSelected: [],
      timelineSegmentByTime: {},

      timelineSegmentListAdded: [],
      timelineSegmentListDeleted: [],
      isLoading: false,
    };
  },
  getters: {
    all(state) {
      return state.timelineSegmentList.map((id) => state.timelineSegments[id]);
    },
    forTimeline(state) {
      return (timeline_id) => {
        return state.timelineSegmentList
          .map((id) => state.timelineSegments[id])
          .filter((e) => e.timeline_id === timeline_id)
          .sort((a, b) => a.start - b.start);
      };
    },
    forTimelineTimeRange(state) {
      return (timeline_id, start, end) => {
        console.log(`${timeline_id}, ${start}, ${end}`);
        return state.timelineSegmentList
          .map((id) => state.timelineSegments[id])
          .filter((e) => e.timeline_id === timeline_id)
          .filter((e) => Math.min(e.end, end) - Math.max(e.start, start) > 0)
          .sort((a, b) => a.start - b.start);
      };
    },
    forTime(state) {
      return (current_time) => {
        return state.timelineSegmentList
          .map((id) => state.timelineSegments[id])
          .filter((e) => e.start <= current_time && e.end >= current_time);
      };
    },
    get(state) {
      return (id) => {
        return state.timelineSegments[id];
      };
    },
    selected(state) {
      return state.timelineSegmentListSelected.map(
        (id) => state.timelineSegments[id]
      );
    },
    lastSelected(state) {
      if (state.timelineSegmentListSelected.length <= 0) {
        return null;
      }
      return state.timelineSegmentListSelected.map(
        (id) => state.timelineSegments[id]
      )[state.timelineSegmentListSelected.length - 1];
    },
    forTimeLUT(state) {
      return (time) => {
        const timeSecond = Math.round(time);
        if (timeSecond in state.timelineSegmentByTime) {
          const timelineSegmentIds = state.timelineSegmentByTime[timeSecond];
          return timelineSegmentIds.map((id) => {
            return state.timelineSegments[id];
          });
        }
        return [];
      };
    },
    getPreviousOnTimeline(state) {
      return (id) => {
        const startTime = state.timelineSegments[id].start;
        const timelineId = state.timelineSegments[id].timeline_id;
        const segments = this.forTimeline(timelineId)
          .filter((e) => e.end <= startTime)
          .sort((a, b) => a.end - b.end);
        if (segments.length <= 0) {
          return null;
        }
        return segments[segments.length - 1];
      };
    },
    getNextOnTimeline(state) {
      return (id) => {
        const endTime = state.timelineSegments[id].end;
        const timelineId = state.timelineSegments[id].timeline_id;
        const segments = this.forTimeline(timelineId)
          .filter((e) => e.start >= endTime)
          .sort((a, b) => a.end - b.end);
        if (segments.length <= 0) {
          return null;
        }
        return segments[0];
      };
    },
  },
  actions: {
    clearSelection() {
      this.timelineSegmentListSelected = [];
      // this.timelineSegmentList.forEach((id) => {
      //     this.timelineSegments[id].selected = false;
      // })
    },
    addToSelection(timelineSegmentId) {
      this.timelineSegmentListSelected.push(timelineSegmentId);
      // if (timelineSegmentId in this.timelineSegments) {
      //     this.timelineSegments[timelineSegmentId].selected = true;
      // }
    },
    removeFromSelection(timelineSegmentId) {
      let segment_index = this.timelineSegmentListSelected.findIndex(
        (f) => f === timelineSegmentId
      );
      this.timelineSegmentListSelected.splice(segment_index, 1);

      // if (timelineSegmentId in this.timelineSegments) {
      //     this.timelineSegments[timelineSegmentId].selected = false;
      // }
    },
    async annotateSegments({ timelineSegmentIds, annotations }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      const params = {
        timeline_segment_ids: timelineSegmentIds,
        annotations: annotations,
      };

      return axios
        .post(`${config.API_LOCATION}/timeline/segment/annotate`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            const timelineSegmentAnnotationStore =
              useTimelineSegmentAnnotationStore();
            const annotationCategoryStore = useAnnotationCategoryStore();
            const annotationStore = useAnnotationStore();

            timelineSegmentAnnotationStore.deleteFromStore(
              res.data.timeline_segment_annotation_deleted
            );
            timelineSegmentAnnotationStore.addToStore(
              res.data.timeline_segment_annotation_added
            );

            annotationCategoryStore.addToStore(
              res.data.annotation_category_added
            );
            annotationStore.addToStore(res.data.annotation_added);

            // let timeline know that something change
            const timelineStore = useTimelineStore();
            timelineSegmentIds.forEach((e) => {
              timelineStore.notifyChanges({
                timelineIds: [this.get(e).timeline_id],
              });
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
    async annotateRange({ timelineId, annotations, start = null, end = null }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      if (!start) {
        const timelineStore = useTimelineStore();
        start = timelineStore.selectedTimeRangeStart;
      }
      if (!end) {
        const timelineStore = useTimelineStore();
        end = timelineStore.selectedTimeRangeEnd;
      }
      const params = {
        timeline_id: timelineId,
        annotations: annotations,
        start: start,
        end: end,
      };

      console.log("#######################")
      return axios
        .post(`${config.API_LOCATION}/timeline/segment/annotate/range`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            console.log("###################++++++")
            const timelineSegmentAnnotationStore =
              useTimelineSegmentAnnotationStore();
            const annotationCategoryStore = useAnnotationCategoryStore();
            const annotationStore = useAnnotationStore();

            this.deleteFromStore(res.data.timeline_segment_deleted);
            this.addToStore(res.data.timeline_segment_added);

            annotationCategoryStore.addToStore(
              res.data.annotation_category_added
            );
            annotationStore.addToStore(res.data.annotation_added);

            timelineSegmentAnnotationStore.deleteFromStore(
              res.data.timeline_segment_annotation_deleted
            );
            console.log("res.data.timeline_segment_annotation_added")
            console.log(JSON.stringify(res.data.timeline_segment_annotation_added))
            timelineSegmentAnnotationStore.addToStore(
              res.data.timeline_segment_annotation_added
            );

            // let timeline know that something change
            const timelineStore = useTimelineStore();
            timelineStore.notifyChanges({ timelineIds: [timelineId] });
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

    async toggle({ timelineSegmentId, annotationId }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      const params = {
        timeline_segment_id: timelineSegmentId,
        annotation_id: annotationId,
      };

      console.log(`timeline_segment::toggle start`);
      const timelineSegmentAnnotationStore =
        useTimelineSegmentAnnotationStore();
      const annotationCategoryStore = useAnnotationCategoryStore();
      const annotationStore = useAnnotationStore();

      return axios
        .post(
          `${config.API_LOCATION}/timeline/segment/annotation/toggle`,
          params
        )
        .then((res) => {
          if (res.data.status === "ok") {
            if ("annotation_added" in res.data) {
              annotationStore.addToStore(res.data.annotation_added);
            }
            if ("annotation_category_added" in res.data) {
              annotationCategoryStore.addToStore(
                res.data.annotation_category_added
              );
            }
            if ("timeline_segment_annotation_deleted" in res.data) {
              timelineSegmentAnnotationStore.deleteFromStore(
                res.data.timeline_segment_annotation_deleted
              );
            }
            if ("timeline_segment_annotation_added" in res.data) {
              timelineSegmentAnnotationStore.addToStore(
                res.data.timeline_segment_annotation_added
              );
            }

            // let timeline know that something change
            const timelineStore = useTimelineStore();
            timelineStore.notifyChanges({
              timelineIds: [this.get(timelineSegmentId).timeline_id],
            });

            console.log(`timeline_segment::toggle end`);
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
    async split({ timelineSegmentId, time }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      const params = {
        timeline_segment_id: timelineSegmentId,
        time: time,
      };
      return axios
        .post(`${config.API_LOCATION}/timeline/segment/split`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            const timelineId = this.get(timelineSegmentId).timeline_id;
            const timelineSegmentAnnotationStore =
              useTimelineSegmentAnnotationStore();

            timelineSegmentAnnotationStore.deleteFromStore(
              res.data.timeline_segment_annotation_deleted
            );
            timelineSegmentAnnotationStore.addToStore(
              res.data.timeline_segment_annotation_added
            );
            this.deleteFromStore(res.data.timeline_segment_deleted);
            this.addToStore(res.data.timeline_segment_added);

            // let timeline know that something change
            const timelineStore = useTimelineStore();
            timelineStore.notifyChanges({ timelineIds: [timelineId] });
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
    async merge({ timelineSegmentIds }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      const params = {
        timeline_segment_ids: timelineSegmentIds,
      };
      return axios
        .post(`${config.API_LOCATION}/timeline/segment/merge`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            const timelineSegmentAnnotationStore =
              useTimelineSegmentAnnotationStore();

            timelineSegmentAnnotationStore.deleteFromStore(
              res.data.timeline_segment_annotation_deleted
            );
            timelineSegmentAnnotationStore.addToStore(
              res.data.timeline_segment_annotation_added
            );

            const timelineStore = useTimelineStore();

            const timelineIds = [
              ...new Set(
                timelineSegmentIds.map((id) => this.get(id).timeline_id)
              ),
            ];
            timelineStore.notifyChanges({ timelineIds: timelineIds });

            this.deleteFromStore(res.data.timeline_segment_deleted);
            this.addToStore(res.data.timeline_segment_added);

            // update shot list
            const shotStore = useShotStore();
            shotStore.shots();
          }
          // let timeline know that something change
        })
        .finally(() => {
          this.isLoading = false;
        });
      // .catch((error) => {
      //     const info = { date: Date(), error, origin: 'collection' };
      //     commit('error/update', info, { root: true });
      // });
    },
    async fetchForVideo({ timelineId, videoId, clear = true }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      let params = {};
      if (timelineId) {
        params.timeline_id = timelineId;
      }
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
        .get(`${config.API_LOCATION}/timeline/segment/list`, { params })
        .then((res) => {
          if (res.data.status === "ok") {
            this.updateStore(res.data.entries);
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
    clearStore() {
      this.timelineSegmentListSelected = [];
      this.timelineSegmentByTime = {};

      this.timelineSegmentListAdded = [];
      this.timelineSegmentListDeleted = [];
      this.timelineSegments = {};
      this.timelineSegmentList = [];
    },
    addAnnotation(annotations) {
      annotations.forEach((e) => {
        this.timelineSegments[e.timelineSegmentId].annotation_ids.push(
          e.entry.id
        );
      });
    },
    deleteAnnotation(timeline_segment_annotations) {
      timeline_segment_annotations.forEach((f) => {
        this.timelineSegmentList
          .map((id) => this.timelineSegments[id])
          .forEach((e) => {
            let index = e.annotation_ids.findIndex((k) => k === f);
            if (index >= 0) {
              e.annotation_ids.splice(index, 1);
            }
          });
      });
    },
    addToStore(timelineSegments) {
      timelineSegments.forEach((e) => {
        this.timelineSegmentListAdded.push(e.id);
        this.timelineSegments[e.id] = e;
        this.timelineSegmentList.push(e.id);
      });
      timelineSegments = timelineSegments.sort((a, b) => {
        return a.start - b.start;
      });
      this.updateTimeStore();
    },
    deleteFromStore(ids) {
      ids.forEach((id) => {
        this.timelineSegmentListDeleted.push(id);
        // delete from selected
        let index = this.timelineSegmentListSelected.findIndex((f) => f === id);
        this.timelineSegmentListSelected.splice(index, 1);
        // delete from store
        index = this.timelineSegmentList.findIndex((f) => f === id);
        this.timelineSegmentList.splice(index, 1);

        delete this.timelineSegments[id];
      });
      this.updateTimeStore();
    },
    updateStore(timelineSegments) {
      timelineSegments = timelineSegments.sort((a, b) => {
        return a.start - b.start;
      });
      timelineSegments.forEach((e) => {
        if (e.id in this.timelineSegments) {
          return;
        }
        this.timelineSegmentListAdded.push(e.id);
        this.timelineSegments[e.id] = e;
        this.timelineSegmentList.push(e.id);
      });
      this.updateTimeStore();
    },
    deleteTimeline(timeline_id) {
      const timeline_indexes = this.timelineSegmentList
        .map((id) => this.timelineSegments[id])
        .filter((e) => e.timeline_id === timeline_id);
      timeline_indexes.forEach((e) => {
        let segment_index = this.timelineSegmentList.findIndex(
          (f) => f === e.id
        );
        this.timelineSegmentList.splice(segment_index, 1);
        Vue.delete(this.timelineSegments, e.id);
      });
      this.updateTimeStore();
    },

    updateTimeStore() {
      this.all.forEach((e) => {
        for (var i = Math.floor(e.start); i < Math.ceil(e.end); i++) {
          if (i in this.timelineSegmentByTime) {
            this.timelineSegmentByTime[i].push(e.id);
          } else {
            this.timelineSegmentByTime[i] = [e.id];
          }
        }
      });
    },
  },
});
