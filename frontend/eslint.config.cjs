const globals = require("globals");
const pluginVue = require("eslint-plugin-vue");
const js = require("@eslint/js");

module.exports = [
    js.configs.recommended,
    ...pluginVue.configs["flat/recommended"],
    {
        languageOptions: {
            globals: {
                ...globals.browser,
                ...globals.node,
            },
            ecmaVersion: "latest",
            sourceType: "module",
        },

        rules: {
            "vue/multi-word-component-names": "off",
            "vue/no-v-html": "warn",
            "no-console": "off",

            "no-unused-vars": ["error", {
                argsIgnorePattern: "^_",
            }],
        },
    },
    {
        ignores: [
            "**/node_modules/",
            "**/dist/",
            "**/coverage/",
            "**/*.config.js",
            "**/*.spec.js",
            "**/*.test.js",
        ],
    },
];
