printf 'version: %s\nsource: https://www.npmjs.com/package/pi-web-access\n' "$(curl -sSf https://registry.npmjs.org/pi-web-access/latest | jq -r .version)" > answer.md
