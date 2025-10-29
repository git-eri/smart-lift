# build stage
FROM node:24.1-slim AS build-stage
WORKDIR /code
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# production stage
FROM nginx:stable-alpine AS production-stage
WORKDIR /code
COPY --from=build-stage /code/dist /usr/share/nginx/html
COPY nginx.template.conf /etc/nginx/templates/nginx.template.conf
EXPOSE 8080
CMD ["nginx -g 'daemon off;'"]
