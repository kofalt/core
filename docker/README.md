# How to set up a development instance of the api
- Run the live.sh script
- The api is populated with an admin user with an api key of 'change-me'

- To use the sdk to interact with the api:
```
import flywheel

fw = flywheel.Client('localhost:8080:__force_insecure:change-me')
fw.get_current_user()
```
