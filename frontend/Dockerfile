# build stage
FROM node:lts-alpine AS build-stage

ARG VITE_USE_SSL
ARG VITE_BACKEND_PORT
ENV VITE_USE_SSL=$VITE_USE_SSL
ENV VITE_BACKEND_PORT=$VITE_BACKEND_PORT

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# production stage
FROM nginx:stable-alpine AS production-stage
COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]