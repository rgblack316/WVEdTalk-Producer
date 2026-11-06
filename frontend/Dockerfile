# Frontend image: build the Vite SPA, then serve it with nginx + /api proxy.
# Node 26 is the current LTS (vitest 5 / vite 8 need Node >= 22.12). Bump deliberately, not via a floating tag.
FROM node:26-alpine AS build
WORKDIR /app
# Node 25+ images no longer ship yarn; install the classic (v1) CLI the lockfile was made with.
RUN npm install -g yarn@1.22.22
# yarn.lock* (glob) so the build still works if the lockfile isn't present in the repo; prefer a
# frozen install when it is, otherwise fall back to a normal resolve.
COPY package.json yarn.lock* ./
RUN yarn install --frozen-lockfile || yarn install
COPY . .
RUN yarn build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
