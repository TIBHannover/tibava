<template>
  <v-container class="d-flex flex-column">
    <v-row ref="videocontainer" class="video-container">
      <video
        class="video-player"
        ref="video"
        v-on:timeupdate="onTimeUpdate"
        v-on:ended="onEnded"
        v-on:click="toggle"
        v-on:play="onPlay"
        v-on:pause="onPause"
        v-on:loadeddata="onLoadedData"
        v-on:canplay="onCanPlay"
        v-on:resize="onResize"
        :src="playerStore.videoUrl"
      >
        <!-- <source :src="video.url" type="video/mp4" /> -->
      </video>
    </v-row>

    <v-row class="video-control mt-6">
      <v-btn @click="deltaSeek(-1)" small>
        <v-icon> mdi-skip-backward</v-icon>
      </v-btn>
      <v-btn @click="deltaSeek(-0.01)" small>
        <v-icon> mdi-skip-previous</v-icon>
      </v-btn>
      <v-btn @click="toggle" small>
        <v-icon v-if="ended"> mdi-restart</v-icon>
        <v-icon v-else-if="playing"> mdi-pause</v-icon>
        <v-icon v-else> mdi-play</v-icon>
      </v-btn>

      <v-btn @click="deltaSeek(0.01)" small>
        <v-icon> mdi-skip-next</v-icon>
      </v-btn>
      <v-btn @click="deltaSeek(1)" small>
        <v-icon> mdi-skip-forward</v-icon>
      </v-btn>
      <v-btn @click="toggleSyncTime()" small>
        <v-icon v-if="syncTime"> mdi-link</v-icon>
        <v-icon v-else> mdi-link-off</v-icon>
      </v-btn>
      <div class="time-code flex-grow-1 flex-shrink-0">
        {{ get_timecode(currentTime) }}
      </div>
      <v-menu offset-y top>
        <template v-slot:activator="{ on, attrs }">
          <v-btn v-bind="attrs" v-on="on" small>
            {{ currentSpeed.title }}
          </v-btn>
        </template>

        <v-list>
          <v-list-item v-for="(item, index) in speeds" :key="index">
            <v-list-item-title v-on:click="onSpeedChange(index)">{{
              item.title
            }}</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
      <!-- <v-btn small>
        <v-icon>mdi-repeat</v-icon>
      </v-btn> -->
      <v-btn @click="onToggleVolume" small>
        <v-icon v-if="volume > 66"> mdi-volume-high </v-icon>
        <v-icon v-else-if="volume > 33"> mdi-volume-medium </v-icon>
        <v-icon v-else-if="volume > 0"> mdi-volume-low </v-icon>
        <v-icon v-else-if="volume == 0"> mdi-volume-mute </v-icon>
      </v-btn>
      <v-slider
        :value="volume"
        @input="onVolumeChange"
        max="100"
        min="0"
        hide-details
      ></v-slider>
    </v-row>

    <v-row>
      <v-slider
        class="progress-bar"
        :value="100 * progress"
        v-on:change="onSeek"
        hide-details
      ></v-slider>
    </v-row>
  </v-container>
</template>

<script>
import TimeMixin from "../mixins/time";

import { mapStores } from "pinia";
import { usePlayerStore } from "@/store/player";

export default {
  mixins: [TimeMixin],
  data() {
    return {
      currentSpeed: { title: "1.00", value: 1.0 },
      speeds: [
        { title: "0.25", value: 0.25 },
        { title: "0.50", value: 0.5 },
        { title: "0.75", value: 0.75 },
        { title: "1.00", value: 1.0 },
        { title: "1.25", value: 1.25 },
        { title: "1.50", value: 1.5 },
        { title: "1.75", value: 1.75 },
        { title: "2.00", value: 2.0 },
      ],
      observer: undefined
    };
  },
  mounted() {
    const threshold = 0.1
    this.observer = new IntersectionObserver(([e]) => {
        this.$refs.video.classList.toggle('sticky-video', e.intersectionRatio < threshold);
      },
      {threshold: [threshold]}
    );
    this.observer.observe(this.$refs.videocontainer);
  },
  beforeDestroy() {
    this.observer.disconnect();
  },
  methods: {
    toggle() {
      this.playerStore.togglePlaying();
    },
    toggleSyncTime() {
      this.playerStore.toggleSyncTime();
    },
    deltaSeek(delta) {
      this.playerStore.setCurrentTime(this.$refs.video.currentTime + delta);
      this.$refs.video.currentTime += delta;
    },
    onEnded() {
      this.playerStore.setEnded(true);
      this.playerStore.setPlaying(false);
    },
    onPause() {
      this.playerStore.setPlaying(false);
    },
    onPlay() {
      this.playerStore.setEnded(false);
      this.playerStore.setPlaying(true);
    },
    onTimeUpdate(event) {
      this.playerStore.setCurrentTime(event.srcElement.currentTime);
      this.playerStore.setEnded(event.srcElement.ended);
    },
    onSeek(percentage) {
      const targetTime = (this.duration * percentage) / 100;
      this.$refs.video.currentTime = targetTime;
    },
    onSpeedChange(idx) {
      this.currentSpeed = this.speeds[idx];
      this.$refs.video.playbackRate = this.currentSpeed.value;
    },
    onToggleVolume() {
      this.playerStore.toggleMute();
    },
    onVolumeChange(volume) {
      this.playerStore.setVolume(volume);
    },
    onLoadedData() {
      this.$emit("loadedData");
    },
    onCanPlay() {
      this.$emit("canPlay");
    },
    onResize() {
      this.$emit("resize");
    },
  },
  computed: {
    progress() {
      if (this.duration <= 0) {
        return 0;
      }
      return this.playerStore.currentTime / this.playerStore.video.duration;
    },
    volume() {
      return this.playerStore.volume;
    },
    ended() {
      return this.playerStore.ended;
    },
    currentTime() {
      return this.playerStore.currentTime;
    },
    targetTime() {
      return this.playerStore.targetTime;
    },
    playing() {
      return this.playerStore.playing;
    },
    duration() {
      return this.playerStore.videoDuration;
    },
    syncTime() {
      return this.playerStore.syncTime;
    },
    ...mapStores(usePlayerStore),
  },
  watch: {
    targetTime(targetTime) {
      const delta = 1 / this.playerStore.videoFPS; // small delta to prevent showing a frame of the previous shot
      if (this.syncTime) {
        this.$refs.video.currentTime = targetTime + delta;
      }
    },
    playing(playing) {
      if (playing) {
        this.$refs.video.volume = this.volume / 100;
        this.$refs.video.play();
      } else {
        this.$refs.video.pause();
      }
    },
    volume(volume) {
      this.$refs.video.volume = volume / 100;
    },
  },
};
</script>

<style>
.sticky-video {
  position: fixed;
  height: auto !important;
  width: 15vw !important;
  z-index: 3;
  min-height: unset !important;
  top: 80px;
  right: 15px;
}
.video-player {
  max-width: 100%;
  height: 100%;
  max-height: 100%;
  min-height: 480px;
  background-color: black;
}

.video-control {
  gap: 5px;
  /* margin-top: 5px;
  margin-bottom: 0px; */
  /* max-width: 100%; */
}

.video-control > .progress-bar {
  margin-top: auto;
  margin-bottom: auto;
}

.video-control > .time-code {
  margin-top: auto;
  margin-bottom: auto;
}

.video-container {
  background-color: black;
  justify-content: center;
  max-height: 100%;
  min-height: 480px;
}
</style>
