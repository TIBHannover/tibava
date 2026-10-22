import axios from "../plugins/axios";
import config from "../../app.config";
import { defineStore } from "pinia";

import { usePlayerStore } from "./player";
import { usePluginRunStore } from "./plugin_run";
import { useTimelineStore } from "./timeline";
import { useTimelineSegmentStore } from "@/store/timeline_segment";
import { useAnnotationCategoryStore } from "@/store/annotation_category";
import { useAnnotationStore } from "@/store/annotation";

export const useTranscriptStore = defineStore("transcript", {
  state: () => {
    return {
      isLoading: false,
      selectedTranscript: null,
    };
  },
  getters: {
    transcriptList() {
      const timelineStore = useTimelineStore();
      const playerStore = usePlayerStore();

      console.log(JSON.stringify(timelineStore.forVideo(playerStore.videoId)));

      let timeline = timelineStore.forVideo(playerStore.videoId).filter((e) => {
        return e.type == "TRANSCRIPT";
      });
      console.log(JSON.stringify(timeline));

      if (timeline.length) {
        return timeline.map((e, i) => {
          return {
            index: e.id,
            name: e.name,
          };
        });
      }

      return [];
    },
    transcript(state) {
      const timelineStore = useTimelineStore();
      const timelineSegmentStore = useTimelineSegmentStore();
      const playerStore = usePlayerStore();

      const annotationCatygoryStore = useAnnotationCategoryStore();
      const annotationStore = useAnnotationStore();

      let results = [];

      let selectedTranscript = state.selectedTranscript;
      console.log(selectedTranscript);
      if (!state.selectedTranscript) {
        let timeline = timelineStore
          .forVideo(playerStore.videoId)
          .filter((e) => {
            return e.type == "TRANSCRIPT";
          });

        if (!timeline.length) {
          console.error("Transcript: No transcript timeline");
          return results;
        }
        selectedTranscript = timeline[0].id;
      }

      results = timelineSegmentStore
        .forTimeline(selectedTranscript)
        .map((e) => {
          console.log(JSON.stringify(e));
          const name = (e.annotations || [])
            .map((item) => item.annotation?.name)
            .filter(Boolean)
            .join(" ");
          // if (e.annotations.) {
          //   annotation = annotationStore.get(e.annotation_id);
          // }
          // let cat = null;
          // if (annotation) {
          //   cat = annotationCatygoryStore.get(annotation.category_id);
          // }
          // let name = "";
          // if (annotation) {
          //   name = annotation.name;
          // }
          return {
            name: name,
            start: e.start,
            end: e.end,
          };
        });

      return results;
    },
  },
  actions: {
    async setSelectedTranscript({ videoId = null, transcriptTimeline = null }) {
      console.log("SET TRANSCRIPT");
      console.log(transcriptTimeline);
      this.selectedTranscript = transcriptTimeline;

      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      //use video id or take it from the current video
      let params = { timeline_id: transcriptTimeline };
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
        .post(
          `${config.API_LOCATION}/video/analysis/setselectedtranscript`,
          params
        )
        .then((res) => {
          if (res.data.status === "ok") {
          }
        })
        .catch(() => {})
        .finally(() => {
          this.isLoading = false;
        });
    },
    async fetchForVideo({ videoId = null }) {
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
      return axios
        .get(`${config.API_LOCATION}/video/analysis/get`, { params })
        .then((res) => {
          if (res.data.status === "ok") {
            let selectedShots = res.data.entry.selected_shots;
            if (!selectedShots) {
              let timeline = timelineStore
                .forVideo(playerStore.videoId)
                .filter((e) => {
                  return e.type == "TRANSCRIPT";
                });

              if (!timeline.length) {
                console.error("Transcript: No transcript timeline");
                return results;
              }
              selectedShots = timeline[0].id;
            }

            this.selectedShots = selectedShots;

            console.log("selectedShots " + this.selectedShots);
          }
        })
        .catch(() => {})
        .finally(() => {
          this.isLoading = false;
        });
      // .catch((error) => {
      //     const info = { date: Date(), error, origin: 'collection' };
      //     commit('error/update', info, { root: true });
      // });
    },
  },
});
