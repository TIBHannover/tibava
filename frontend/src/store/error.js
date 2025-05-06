import axios from "../plugins/axios";
import config from "../../app.config";

import { defineStore } from "pinia";
// useStore could be anything like useUser, useCart
// the first argument is a unique id of the store across your application
export const useErrorStore = defineStore("error", {
    // other options...
    state: () => {
        return {
            error_component: null,
            error_code: null,
            error_date: null,
            error: false
        };
    },
    getters: {
        errorMessage(state) {
            return "(" + state.error_date + ") " + state.error_component + ": " + state.error_code;
        },

    },
    actions: {
        setError(component, code) {
            this.error_component = component;
            this.error_code = code;
            this.error_date = new Date();
            this.error = true;
        },
    }
});
