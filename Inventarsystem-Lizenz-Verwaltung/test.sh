curl -i -X POST "http://127.0.0.1:5000/validate__information" \
  -H "Content-Type: application/json" \
  -d '{"license":"npEDI1JVhyisQ2dg-fWTTAn5H1hg3eS80Zc-4IptWIU=","hwid":""}'

curl -i -X POST "http://127.0.0.1:5000/validate__information" \
  -H "Content-Type: application/json" \
  -d '{"license":"npEDI1JVhyisQ2dg-fWTTAn5H1hg3eS80Zc-4IptWIU=","hwid":"0c27aefd7107396933c7363efa38fb6c297aa3db119c1597952c05d947f4f27c"}'

curl -i -X POST "http://127.0.0.1:5000/validate__information" \
  -H "Content-Type: application/json" \
  -d '{"license":"npEDI1JVhyisQ2dg-fWTTAn5H1hg3eS80Zc-4IptWIU=","hwid":"0c27aefd7107396933c7363efa38fb6c297aa3db119c1597952c05d947f4f37c"}'