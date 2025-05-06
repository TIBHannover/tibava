import Vue from 'vue'
import App from './App.vue'
import vuetify from '@/plugins/vuetify';
// import store from '@/store';
import i18n from '@/plugins/i18n';

import './styles/custom.css';

import { createPinia, PiniaVuePlugin } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import { useUserStore } from "@/store/user"


Vue.use(PiniaVuePlugin)
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)



import router from '@/router';

var app = Vue.extend({

  async created() {
    const userStore = useUserStore()
    await userStore.getCSRFToken()
    await userStore.getUserData()
  },
})

new app({
  pinia,
  vuetify,
  router,
  i18n,
  render: h => h(App),
}).$mount('#app')

import Router from "vue-router";
Vue.use(Router)