<template>
  <v-card
  :class="['d-flex', 'flex-column', 'pa-2', 'ma-4', { highlighted: isHighlighted }]"
  elevation="4"
  height="120"
  v-on:click="setVideoPlayerTime(transcript.start)"
  >
    <span style="margin-bottom:0.2cm">{{ get_timecode(transcript.start, 0) }}</span>
    <v-tooltip top open-delay="200">
    <template v-slot:activator="{ on, attrs }">
      <span
        v-bind="attrs"
        v-on="on"
        class="mx-0"
        style="overflow: hidden; color:rgb(0, 0, 0);"
        >
        {{ transcript.name }}
        </span
      ></template
    >
    <span>{{transcript.name}}</span>
  </v-tooltip>
  </v-card>

</template>

<script>
import TimeMixin from "../mixins/time";

import { mapStores } from "pinia";
import { usePlayerStore } from "@/store/player";

export default {
  mixins: [TimeMixin],
  props: ["transcript"],
  data () {
    return {
      // this variable ensures that the signal to scroll is only emitted once 
      emitted: false
    }
  },
  methods: {
    setVideoPlayerTime(time) {
      this.playerStore.setTargetTime(time);
    },
  },
  computed: {
    isHighlighted() {
      const cur_time = this.playerStore.currentTime;
      return this.transcript.start <= cur_time && this.transcript.end > cur_time;
    },
    time(){
      return this.playerStore.currentTime;
    },
    syncTime() {
      return this.playerStore.syncTime;
    },
    ...mapStores(usePlayerStore),
  },
  watch: {
    isHighlighted(newVal) {
        if (newVal && !this.emitted && this.syncTime){
          this.$emit('childHighlighted', this.transcript.id);
        }
        this.emitted = newVal;
      }
    }
};
</script>

<style>
.highlighted {
  background-color: rgba(43, 24, 27, 0.287) !important
}
.v-tooltip__content {
max-width: 400px; /* Set your desired maximum width */
}
</style> 
