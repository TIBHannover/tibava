<template>
  <div>
    <v-menu min-width="175" offset-y bottom left>
      <!-- open-on-hover close-delay -->
      <template v-slot:activator="{ attrs }">
        <v-btn tile text v-bind="attrs" @click="showModalExport = true" class="ml-n2">
          <v-icon color="primary">mdi-swap-vertical-bold</v-icon>
          Export
        </v-btn>
      </template>
    </v-menu>

    <ModalExport v-model="showModalExport"> </ModalExport>
  </div>
</template>

<script>
import ModalExport from "@/components/ModalExport.vue";

import { mapStores } from "pinia";
import { useUserStore } from "@/store/user";
import { usePlayerStore } from "@/store/player";

export default {
  data() {
    return {
      showModalExport: false,
    };
  },
  computed: {
    videoId() {
      const videoId = this.playerStore.videoId;
      return videoId;
    },
    loggedIn() {
      return this.userStore.loggedIn;
    },

    ...mapStores(useUserStore, usePlayerStore),
  },
  components: {
    ModalExport,
  },
};
</script>

<style>
.v-menu__content .v-btn:not(.accent) {
  text-transform: capitalize;
  justify-content: left;
}

.v-btn:not(.v-btn--round).v-size--large {
  height: 48px;
}
</style>
