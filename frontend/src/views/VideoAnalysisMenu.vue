<template>
  <div class="menu">
    <ModalPlugin :videoIds="selectedVideos" />
    <History />
    <AnnotationMenu />
    <VideoMenu />
    <UserMenu />
  </div>
</template>

<script>
import VideoMenu from "@/components/VideoMenu.vue";
import ModalPlugin from "@/components/ModalPlugin.vue";
import AnnotationMenu from "@/components/AnnotationMenu.vue";
import UserMenu from "@/components/UserMenu.vue";
import History from "@/components/History.vue";
import { mapStores } from "pinia";
import { useUserStore } from "@/store/user";
import { useVideoStore } from "@/store/video";
import { usePlayerStore } from "@/store/player";
import { useErrorStore } from "@/store/error";

export default {
  data() {
    return {};
  },
  computed: {
    selectedVideos() {
      return this.videoStore.videoSelected;
    },
    ...mapStores(useUserStore, usePlayerStore, useErrorStore, useVideoStore),
  },
  components: {
    VideoMenu,
    ModalPlugin,
    AnnotationMenu,
    History,
    UserMenu,
  },
};
</script>

<style scoped>
.menu * {
  margin-right: 10px;
}
.menu {
  display: flex;
}
</style>
