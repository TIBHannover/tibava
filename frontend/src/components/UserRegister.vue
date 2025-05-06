<template>
  <v-dialog v-model="dialog" max-width="350px">
    <v-card class="register">
      <v-card-title>
        {{ $t("user.register.title") }}

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
          v-model="user.email"
          :placeholder="$t('user.email')"
          prepend-icon="mdi-email"
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

      <v-card-actions class="px-6 pb-6">
        <v-btn
          @click="register"
          :disabled="disabled"
          color="accent"
          block
          rounded
          depressed
        >
          {{ $t("user.register.title") }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
import { mapStores } from "pinia";
import { useUserStore } from "@/store/user";

export default {
  props: ["value"],
  data() {
    return {
      user: {},
      dialog: false,
      showPassword: false,
      error_message: ""
    };
  },
  methods: {
    async register() {
      const status = await this.userStore.register(this.user);
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
          return this.$t("user.register.rules.min");
        }

        if (value.length > 50) {
          return this.$t("user.register.rules.max");
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

        if (total === 3) return false;
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
};
</script>
