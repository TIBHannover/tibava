<template>
  <div>
    <v-menu v-model="menu" min-width="175" offset-y bottom left>
      <template v-slot:activator="{ attrs, on: menu }">
        <v-btn
          tile
          text
          v-bind="attrs"
          v-on="menu"
          class="ml-n2"
          :title="$t('user.menu.title')"
        >
          <v-icon color="primary">mdi-account-circle</v-icon>

          <v-badge v-if="loggedIn" color="accent" dot> {{ username }} </v-badge>
          <span v-else> Login </span>
        </v-btn>
      </template>

      <UserAccount v-if="loggedIn" />

      <v-list v-else class="pa-0">
        <v-list-item @click="showModalLogin = true">
          <v-list-item-title>{{ $t("user.login.title") }}</v-list-item-title>
        </v-list-item>

        <v-list-item @click="showModalRegister = true">
          <v-list-item-title>{{ $t("user.register.title") }}</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-menu>
    <UserLogin v-model="showModalLogin">
      <activator />
    </UserLogin>
    <UserRegister v-model="showModalRegister">
      <activator />
    </UserRegister>
  </div>
</template>

<script>
import UserLogin from "@/components/UserLogin.vue";
import UserAccount from "@/components/UserAccount.vue";
import UserRegister from "@/components/UserRegister.vue";

import { mapStores } from "pinia";
import { useUserStore } from "@/store/user";

export default {
  data() {
    return {
      menu: false,
      showModalLogin: false,
      showModalRegister: false,
    };
  },
  computed: {
    username() {
      return this.userStore.username;
    },
    loggedIn() {
      return this.userStore.loggedIn;
    },

    ...mapStores(useUserStore),
  },
  components: {
    UserLogin,
    UserAccount,
    UserRegister,
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