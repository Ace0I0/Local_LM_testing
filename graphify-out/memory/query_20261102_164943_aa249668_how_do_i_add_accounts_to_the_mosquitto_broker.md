---
type: "query"
date: "2026-11-02T16:49:43.280803+00:00"
question: "how do i add accounts to the mosquitto broker?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Mosquitto Setup Wizard", "ensure_mqtt_user()", "setup_mosquitto.sh"]
---

# Q: how do i add accounts to the mosquitto broker?

## Answer

Expanded from original query via graph vocab: [mosquitto, broker, account, user, password, credentials, setup, wizard]. This project stores hashed credentials in /etc/mosquitto/artemis.passwd and authorization rules in /etc/mosquitto/artemis.acl. Add a user interactively with sudo mosquitto_passwd /etc/mosquitto/artemis.passwd USERNAME, add a matching user/topic ACL stanza, then restart Mosquitto. Do not pass -c for an existing password file because it recreates the file. The setup wizard already creates artemis_test, esphome_living_room, homeassistant, and artemis, but rerunning it rewrites the Artemis ACL to those built-in entries.

## Outcome

- Signal: useful

## Source Nodes

- Mosquitto Setup Wizard
- ensure_mqtt_user()
- setup_mosquitto.sh