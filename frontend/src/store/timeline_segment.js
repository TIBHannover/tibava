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

function sanitizeAnnotations(annotations) {
  if (!Array.isArray(annotations)) return [];
  return annotations.map((item) => {
    if (typeof item === "string") return item;
    return {
      name: item.name,
      color: item.color,
      ...(item.id ? { id: item.id } : {}),
      category: item.category
        ? {
            name: item.category.name,
            color: item.category.color,
            ...(item.category.id ? { id: item.category.id } : {}),
          }
        : null,
    };
  });
}

function syncUpdatedEntities(resData) {
  const annotationCategoryStore = useAnnotationCategoryStore();
  const annotationStore = useAnnotationStore();

  if (resData.annotation_category_updated) {
    if (typeof annotationCategoryStore.updateInStore === "function") {
      annotationCategoryStore.updateInStore(
        resData.annotation_category_updated
      );
    } else {
      annotationCategoryStore.addToStore(resData.annotation_category_updated);
    }
  }

  if (resData.annotation_updated) {
    if (typeof annotationStore.updateInStore === "function") {
      annotationStore.updateInStore(resData.annotation_updated);
    } else {
      annotationStore.addToStore(resData.annotation_updated);
    }
  }
}

export const useTimelineSegmentStore = defineStore("timelineSegment", {
  state: () => ({
    timelineSegments: {},
    timelineSegmentList: [],
    timelineSegmentListSelected: [],
    timelineSegmentByTime: {},

    timelineSegmentListAdded: [],
    timelineSegmentListDeleted: [],
    isLoading: false,
  }),
  getters: {
    all(state) {
      return state.timelineSegmentList.map((id) => state.timelineSegments[id]);
    },
    forTimeline(state) {
      return (timeline_id) => {
        return state.timelineSegmentList
          .map((id) => state.timelineSegments[id])
          .filter((e) => e && e.timeline_id === timeline_id)
          .sort((a, b) => a.start - b.start);
      };
    },
    forTimelineTimeRange(state) {
      return (timeline_id, start, end) => {
        return state.timelineSegmentList
          .map((id) => state.timelineSegments[id])
          .filter((e) => e && e.timeline_id === timeline_id)
          .filter((e) => Math.min(e.end, end) - Math.max(e.start, start) > 0)
          .sort((a, b) => a.start - b.start);
      };
    },
    forTime(state) {
      return (current_time) => {
        return state.timelineSegmentList
          .map((id) => state.timelineSegments[id])
          .filter((e) => e && e.start <= current_time && e.end >= current_time);
      };
    },
    get(state) {
      return (id) => state.timelineSegments[id];
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
      return state.timelineSegments[
        state.timelineSegmentListSelected[
          state.timelineSegmentListSelected.length - 1
        ]
      ];
    },
    forTimeLUT(state) {
      return (time) => {
        const timeSecond = Math.round(time);
        if (timeSecond in state.timelineSegmentByTime) {
          const timelineSegmentIds = state.timelineSegmentByTime[timeSecond];
          return timelineSegmentIds.map((id) => state.timelineSegments[id]);
        }
        return [];
      };
    },
    getPreviousOnTimeline(state) {
      return (id) => {
        const current = state.timelineSegments[id];
        if (!current) return null;
        const startTime = current.start;
        const timelineId = current.timeline_id;
        const segments = this.forTimeline(timelineId)
          .filter((e) => e.end <= startTime)
          .sort((a, b) => a.end - b.end);
        if (segments.length <= 0) return null;
        return segments[segments.length - 1];
      };
    },
    getNextOnTimeline(state) {
      return (id) => {
        const current = state.timelineSegments[id];
        if (!current) return null;
        const endTime = current.end;
        const timelineId = current.timeline_id;
        const segments = this.forTimeline(timelineId)
          .filter((e) => e.start >= endTime)
          .sort((a, b) => a.start - b.start);
        if (segments.length <= 0) return null;
        return segments[0];
      };
    },
  },
  actions: {
    clearSelection() {
      this.timelineSegmentListSelected = [];
    },
    addToSelection(timelineSegmentId) {
      if (!this.timelineSegmentListSelected.includes(timelineSegmentId)) {
        this.timelineSegmentListSelected.push(timelineSegmentId);
      }
    },
    removeFromSelection(timelineSegmentId) {
      const segment_index = this.timelineSegmentListSelected.findIndex(
        (f) => f === timelineSegmentId
      );
      if (segment_index >= 0) {
        this.timelineSegmentListSelected.splice(segment_index, 1);
      }
    },
    async annotateSegments({ timelineSegmentIds, annotations }) {
      if (this.isLoading) return;
      this.isLoading = true;

      const params = {
        timeline_segment_ids: timelineSegmentIds,
        annotations: sanitizeAnnotations(annotations),
      };

      return axios
        .post(`${config.API_LOCATION}/timeline/segment/annotate`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            const timelineSegmentAnnotationStore =
              useTimelineSegmentAnnotationStore();
            const annotationCategoryStore = useAnnotationCategoryStore();
            const annotationStore = useAnnotationStore();

            // 1. Delete removed segment-annotation links
            if (res.data.timeline_segment_annotation_deleted) {
              timelineSegmentAnnotationStore.deleteFromStore(
                res.data.timeline_segment_annotation_deleted
              );
            }

            // 2. Add newly created segment-annotation links
            if (res.data.timeline_segment_annotation_added) {
              timelineSegmentAnnotationStore.addToStore(
                res.data.timeline_segment_annotation_added
              );
            }

            // 3. Add newly created categories and annotations
            if (res.data.annotation_category_added) {
              annotationCategoryStore.addToStore(
                res.data.annotation_category_added
              );
            }
            if (res.data.annotation_added) {
              annotationStore.addToStore(res.data.annotation_added);
            }

            // 4. Update modified categories and annotations (colors/names)
            syncUpdatedEntities(res.data);

            // 5. Notify unique timelines of updates
            const timelineStore = useTimelineStore();
            const uniqueTimelineIds = [
              ...new Set(
                timelineSegmentIds
                  .map((id) => this.get(id)?.timeline_id)
                  .filter(Boolean)
              ),
            ];
            if (uniqueTimelineIds.length > 0) {
              timelineStore.notifyChanges({ timelineIds: uniqueTimelineIds });
            }
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async annotateRange({ timelineId, annotations, start = null, end = null }) {
      if (this.isLoading) return;
      this.isLoading = true;

      const timelineStore = useTimelineStore();
      if (!start) start = timelineStore.selectedTimeRangeStart;
      if (!end) end = timelineStore.selectedTimeRangeEnd;

      const params = {
        timeline_id: timelineId,
        annotations: sanitizeAnnotations(annotations),
        start: start,
        end: end,
      };

      return axios
        .post(`${config.API_LOCATION}/timeline/segment/annotate/range`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            const timelineSegmentAnnotationStore =
              useTimelineSegmentAnnotationStore();
            const annotationCategoryStore = useAnnotationCategoryStore();
            const annotationStore = useAnnotationStore();

            if (res.data.timeline_segment_deleted) {
              this.deleteFromStore(res.data.timeline_segment_deleted);
            }
            if (res.data.timeline_segment_added) {
              this.addToStore(res.data.timeline_segment_added);
            }

            if (res.data.annotation_category_added) {
              annotationCategoryStore.addToStore(
                res.data.annotation_category_added
              );
            }
            if (res.data.annotation_added) {
              annotationStore.addToStore(res.data.annotation_added);
            }

            // Sync updated colors/categories
            syncUpdatedEntities(res.data);

            if (res.data.timeline_segment_annotation_deleted) {
              timelineSegmentAnnotationStore.deleteFromStore(
                res.data.timeline_segment_annotation_deleted
              );
            }
            if (res.data.timeline_segment_annotation_added) {
              timelineSegmentAnnotationStore.addToStore(
                res.data.timeline_segment_annotation_added
              );
            }

            timelineStore.notifyChanges({ timelineIds: [timelineId] });
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async toggle({ timelineSegmentId, annotationId }) {
      if (this.isLoading) return;
      this.isLoading = true;

      const params = {
        timeline_segment_id: timelineSegmentId,
        annotation_id: annotationId,
      };

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

            syncUpdatedEntities(res.data);

            const timelineStore = useTimelineStore();
            const segment = this.get(timelineSegmentId);
            if (segment) {
              timelineStore.notifyChanges({
                timelineIds: [segment.timeline_id],
              });
            }
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async split({ timelineSegmentId, time }) {
      if (this.isLoading) return;
      this.isLoading = true;

      const params = {
        timeline_segment_id: timelineSegmentId,
        time: time,
      };
      return axios
        .post(`${config.API_LOCATION}/timeline/segment/split`, params)
        .then((res) => {
          if (res.data.status === "ok") {
            const timelineId = this.get(timelineSegmentId)?.timeline_id;
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

            if (timelineId) {
              const timelineStore = useTimelineStore();
              timelineStore.notifyChanges({ timelineIds: [timelineId] });
            }
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async merge({ timelineSegmentIds }) {
      if (this.isLoading) return;
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
                timelineSegmentIds
                  .map((id) => this.get(id)?.timeline_id)
                  .filter(Boolean)
              ),
            ];
            timelineStore.notifyChanges({ timelineIds: timelineIds });

            this.deleteFromStore(res.data.timeline_segment_deleted);
            this.addToStore(res.data.timeline_segment_added);

            const shotStore = useShotStore();
            shotStore.shots();
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async fetchForVideo({ timelineId, videoId, clear = true }) {
      if (this.isLoading) return;
      this.isLoading = true;

      let params = {};
      if (timelineId) {
        params.timeline_id = timelineId;
      }
      if (videoId) {
        params.video_id = videoId;
      } else {
        const playerStore = usePlayerStore();
        const activeVideoId = playerStore.videoId;
        if (activeVideoId) {
          params.video_id = activeVideoId;
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
        if (this.timelineSegments[e.timelineSegmentId]) {
          this.timelineSegments[e.timelineSegmentId].annotation_ids.push(
            e.entry.id
          );
        }
      });
    },
    deleteAnnotation(timeline_segment_annotations) {
      timeline_segment_annotations.forEach((f) => {
        this.timelineSegmentList
          .map((id) => this.timelineSegments[id])
          .filter(Boolean)
          .forEach((e) => {
            if (!Array.isArray(e.annotation_ids)) return;
            const index = e.annotation_ids.findIndex((k) => k === f);
            if (index >= 0) {
              e.annotation_ids.splice(index, 1);
            }
          });
      });
    },
    addToStore(timelineSegments) {
      timelineSegments.forEach((e) => {
        this.timelineSegmentListAdded.push(e.id);
        Vue.set(this.timelineSegments, e.id, e);
        if (!this.timelineSegmentList.includes(e.id)) {
          this.timelineSegmentList.push(e.id);
        }
      });
      this.updateTimeStore();
    },
    deleteFromStore(ids) {
      ids.forEach((id) => {
        this.timelineSegmentListDeleted.push(id);
        const selIdx = this.timelineSegmentListSelected.findIndex(
          (f) => f === id
        );
        if (selIdx >= 0) this.timelineSegmentListSelected.splice(selIdx, 1);

        const listIdx = this.timelineSegmentList.findIndex((f) => f === id);
        if (listIdx >= 0) this.timelineSegmentList.splice(listIdx, 1);

        Vue.delete(this.timelineSegments, id);
      });
      this.updateTimeStore();
    },
    updateStore(timelineSegments) {
      timelineSegments.forEach((e) => {
        if (e.id in this.timelineSegments) {
          Vue.set(this.timelineSegments, e.id, e);
          return;
        }
        this.timelineSegmentListAdded.push(e.id);
        Vue.set(this.timelineSegments, e.id, e);
        this.timelineSegmentList.push(e.id);
      });
      this.updateTimeStore();
    },
    deleteTimeline(timeline_id) {
      const segmentsToDelete = this.timelineSegmentList
        .map((id) => this.timelineSegments[id])
        .filter((e) => e && e.timeline_id === timeline_id);

      segmentsToDelete.forEach((e) => {
        const segment_index = this.timelineSegmentList.findIndex(
          (f) => f === e.id
        );
        if (segment_index >= 0) {
          this.timelineSegmentList.splice(segment_index, 1);
        }
        Vue.delete(this.timelineSegments, e.id);
      });
      this.updateTimeStore();
    },
    updateTimeStore() {
      // Clear LUT before rebuild to avoid duplicate ID accumulation
      this.timelineSegmentByTime = {};

      this.all.forEach((e) => {
        if (!e) return;
        for (let i = Math.floor(e.start); i < Math.ceil(e.end); i++) {
          if (!this.timelineSegmentByTime[i]) {
            this.timelineSegmentByTime[i] = [];
          }
          if (!this.timelineSegmentByTime[i].includes(e.id)) {
            this.timelineSegmentByTime[i].push(e.id);
          }
        }
      });
    },
  },
});
