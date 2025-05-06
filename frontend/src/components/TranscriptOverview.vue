<template>
  <v-card v-if="noTranscripts" elevation="0" :class="['d-flex', 'flex-column', 'pa-2', 'ma-4']">
    <span>There is no transcript. Create it with the <em>Speech Recognition (whisper)</em> pipeline.</span>
  </v-card>
  <div v-else style="height: 100%;">
    <v-text-field
      v-model="search"
      append-icon="mdi-magnify"
      label="Search"
      single-line
      hide-details
      class="ps-7 pe-8 ms-auto me-auto transcript-search"
    ></v-text-field>
    <v-virtual-scroll
      ref="parentContainer"
      :class="['d-flex', 'flex-column', 'pa-2', 'ma-4']"
      :items="transcripts"
      item-height="140"
      :bench="transcriptLength"
      height="100%"
    >
      <template v-slot:default="{ item }">
        <TranscriptCard
          :transcript="item"
          :ref="`childContainer-${item.id}`"
          @childHighlighted="scrollToHighlightedChild"
        />
      </template>
    </v-virtual-scroll>
  </div>
</template>

<script>
import { mapStores } from "pinia";
import TranscriptCard from "@/components/TranscriptCard.vue";
import { useTimelineSegmentAnnotationStore } from "@/store/timeline_segment_annotation";

export default {
  data() {
    return {
      search: "",
    };
  },
  methods: {
    scrollToHighlightedChild(childID) {
      const parentContainer = this.$refs.parentContainer;
      const childContainer = this.$refs[`childContainer-${childID}`];

      if (parentContainer && childContainer) {
        const offset = (parentContainer.$el.offsetHeight - childContainer.$el.offsetHeight) / 2;
        parentContainer.$el.scroll(0, childContainer.$el.parentElement.offsetTop - offset);
      }
    },
  },
  computed: {
    transcriptLength() {
      return this.transcripts.length;
    },
    noTranscripts() {
      return this.timelineSegmentAnnotationStore.transcriptSegments.length === 0;
    }, 
    transcripts() {
      return this.timelineSegmentAnnotationStore.transcriptSegments.filter(
        (t) =>
          this.search == "" ||
          t.name.toLowerCase().includes(this.search.toLowerCase())
      );
    },
    ...mapStores(useTimelineSegmentAnnotationStore),
  },
  components: {
    TranscriptCard,
  },
};
</script>
<style>
.transcript-search {
  max-width: 450px;
}
</style>
