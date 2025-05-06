<template>
  <v-row align="center" justify="center" class="px-2 py-2">
    <v-col cols="12">
      <div class="pa-4">
        <div v-for="(item, i) in current_annotations" :key="i" class="my-2">
          <v-progress-linear :color="item.color" height="30" rounded
            :value="((time - item.start) / (item.end - item.start)) * 100">
            <v-tooltip top>
              <template v-slot:activator="{ on, attrs }">
                <span v-bind="attrs" v-on="on" class="mx-2" style="
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                  ">{{ item.timeline_name }} :: {{ item.name }}</span></template>
              <span>{{ item.timeline_name }} :: {{ item.name }}</span>
            </v-tooltip>
          </v-progress-linear>
        </div>
      </div>
    </v-col>
  </v-row>
</template>


<script>
import TimeMixin from "../mixins/time";

import { mapStores } from "pinia";
import { usePlayerStore } from "../store/player";
import { useTimelineSegmentAnnotationStore } from "../store/timeline_segment_annotation";
import { useAnnotationStore } from "../store/annotation";
import { useTimelineSegmentStore } from "../store/timeline_segment";
import { useTimelineStore } from "../store/timeline";



export default {
  mixins: [TimeMixin],
  computed: {
    annotations() {
      const annotationsMap = {};
      this.timelineSegmentAnnotationStore.all.forEach(annotation => {
        const timelineSegment = this.timelineSegmentStore.get(annotation.timeline_segment_id);
        const annotationData = this.annotationStore.get(annotation.annotation_id);

        annotationsMap[annotation.id] = {
          name: annotationData ? annotationData.name : null,
          timeline_name: this.timelineStore.get(timelineSegment.timeline_id).name,
          color: annotationData ? annotationData.color : "white",
          id: annotation.id,
          start: timelineSegment ? timelineSegment.start : 0,
          end: timelineSegment ? timelineSegment.end : 0
        };
      });

      return annotationsMap;
    },
    annotationsByTime() {
      let lut = {};
      for (let t = 0; t < Math.ceil(this.playerStore.videoDuration); t++) {
        lut[t] = [];
        for (const annotation of Object.values(this.annotations)) {
          if (annotation.start <= t && t < annotation.end) {
            lut[t].push(annotation.id);
          }
        }
      }
      return lut;
    },
    current_annotations() {
      const time = Math.round(this.time);
      return this.annotationsByTime[time].map((id) => this.annotations[id]);
    },
    time() {
      return this.playerStore.currentTime;
    },
    ...mapStores(usePlayerStore, useAnnotationStore, useTimelineStore, useTimelineSegmentAnnotationStore, useTimelineSegmentStore),
  }
};
</script>
