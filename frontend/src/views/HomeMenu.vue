<template>
  <div class="menu">
    <ModalVideoUpload />
    <ModalPlugin :videoIds="selectedVideos">
      <template v-slot:activator="{ on, attrs }">
        <v-btn
          tile
          text
          :disabled="selectedVideos.length == 0"
          v-bind="attrs"
          v-on="on"
        >
          <v-icon>{{ "mdi-plus" }}</v-icon>
          {{ $t("modal.plugin.link") }}
        </v-btn>
      </template>
    </ModalPlugin>
    <UserMenu />
  </div>
</template>

<script>
import ModalVideoUpload from "@/components/ModalVideoUpload.vue";
import ModalPlugin from "@/components/ModalPlugin.vue";
import UserMenu from "@/components/UserMenu.vue";
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
    ModalVideoUpload,
    ModalPlugin,
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
