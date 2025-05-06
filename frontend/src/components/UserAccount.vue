<template>
  <v-list-item-content class="account justify-center pa-10">
    <div class="mx-auto text-center">
      <v-avatar color="secondary">
        <span class="white--text text-h5">{{ initials }}</span>
      </v-avatar>

      <h3 class="mt-5">{{ username }}</h3>
      <p class="text-caption clip mt-2 mb-0" style="max-width: 170px">
        {{ email }}
      </p>
      <p class="text-caption mb-0">
        <i>{{ joined }}</i>
      </p>
    </div>

    <div class="v-btn--absolute v-btn--right v-btn--top">
      <v-btn
        :title="$t('user.logout.title')"
        class="mr-n2 mt-n2"
        @click="logout"
        icon
      >
        <v-icon>mdi-logout-variant</v-icon>
      </v-btn>
    </div>
  </v-list-item-content>
</template>

<script>
import { repPlace } from "../plugins/helpers";

import { mapStores } from "pinia";
import { useUserStore } from "@/store/user";
export default {
  methods: {
    async logout() {
      const loggedOut = await this.userStore.logout();
      if (loggedOut) {
        this.$router.push({ name: 'Home' });
      }
    },
  },
  computed: {
    username() {
      return this.userStore.username;
    },
    email() {
      return this.userStore.email;
    },
    date() {
      return this.userStore.date;
    },
    nDays() {
      const date = new Date(this.date);
      const diffInMs = new Date() - date;
      return Math.round(diffInMs / (1000 * 60 * 60 * 24));
    },
    joined() {
      let text = this.$t("user.menu.joined");
      return repPlace({ n_days: this.nDays }, text);
    },
    initials() {
      return this.username.slice(0, 2);
    },
    ...mapStores(useUserStore),
  },
};
</script>
<style>
.v-list-item__content.account {
  min-width: 250px;
  letter-spacing: 0.0892857143em;
  border-bottom: 1px solid #f5f5f5;
}

.v-menu__content .account .v-btn:not(.accent) {
  justify-content: center;
}

.v-application .v-avatar.secondary {
  background-color: rgba(69, 123, 157, 0.54) !important;
  border-color: rgba(69, 123, 157, 0.54) !important;
}

.account {
  background-color: rgb(255, 255, 255) !important;
}
</style>
