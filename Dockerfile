FROM nginx:alpine
# リポジトリ内の index.html を Nginx の公開ディレクトリにコピー
COPY index.html /usr/share/nginx/html/index.html
