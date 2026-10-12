# Frontend image: build the Vite SPA, then serve it with nginx + /api proxy.
FROM node:20-alpine AS build
WORKDIR /app
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
