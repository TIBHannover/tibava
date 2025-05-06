<template>
  <v-dialog v-model="dialog" max-width="350px">
    <v-card class="login">
      <v-card-title>
        {{ $t("user.login.title") }}

        <v-btn icon @click="dialog = false" absolute right>
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text>
        <v-text-field
          v-model="user.name"
          :placeholder="$t('user.name')"
          prepend-icon="mdi-account"
          counter="50"
          :rules="[checkLength]"
          clearable
        ></v-text-field>

        <v-text-field
          v-model="user.password"
          :append-icon="
            showPassword ? 'mdi-eye-outline' : 'mdi-eye-off-outline'
          "
          :placeholder="$t('user.password')"
          prepend-icon="mdi-lock"
          @click:append="showPassword = !showPassword"
          :type="showPassword ? 'text' : 'password'"
          counter="50"
          :rules="[checkLength]"
          clearable
        ></v-text-field>
        <p v-if="error_message.length>0" class="text-uppercase font-weight-bold red--text">Error: {{ error_message }}</p>
      </v-card-text>

      <v-card-actions class="px-6 pt-2">
        <v-btn
          @click="login"
          :disabled="disabled"
          color="accent"
          block
          rounded
          depressed
        >
          {{ $t("user.login.title") }}
        </v-btn>
      </v-card-actions>

      <div class="grey--text px-6 pb-6" style="text-align: center">
        {{ $t("user.login.text") }}

        <a @click="showModalRegister = true">
          {{ $t("user.register.title") }}
        </a>

        <UserRegister v-model="showModalRegister">
          <activator />
        </UserRegister>
      </div>
    </v-card>
  </v-dialog>
</template>

<script>
import UserRegister from "@/components/UserRegister.vue";

import { mapStores } from "pinia";
import { useUserStore } from "@/store/user";

export default {
  props: ["value"],
  data() {
    return {
      user: {},
      dialog: false,
      showPassword: false,
      showModalRegister: false,
      error_message: ""
    };
  },
  methods: {
    async login() {
      const status = await this.userStore.login(this.user);
      console.log(status)
      if (status.status === "ok") {
        this.dialog = false;
        this.error_message = "";
      } else {
        this.error_message = status.message;
      }
    },
    checkLength(value) {
      if (value) {
        if (value.length < 5) {
          return this.$t("user.login.rules.min");
        }

        if (value.length > 50) {
          return this.$t("user.login.rules.max");
        }

        return true;
      }

      return this.$t("field.required");
    },
  },
  computed: {
    disabled() {
      if (Object.keys(this.user).length) {
        const total = Object.values(this.user).reduce(
          (t, value) => t + (this.checkLength(value) === true),
          0
        );

        if (total === 2) return false;
      }

      return true;
    },
    ...mapStores(useUserStore),
  },
  watch: {
    dialog(value) {
      this.$emit("input", value);
    },
    value(value) {
      if (value) {
        this.dialog = true;
      }
    },
  },
  components: {
    UserRegister,
  },
};
</script>

<style>
.v-card.login .v-btn.register {
  min-width: auto !important;
  text-transform: capitalize;
  display: inline-block;
  letter-spacing: 0;
  font-size: 1rem;
  padding: 0 2px;
  height: 20px;
}

.v-card.login .v-btn.register:before,
.v-card.login .v-btn.register:hover:before,
.v-card.login .v-btn.register:focus:before {
  background-color: transparent;
}
</style>
