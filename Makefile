.PHONY: css css-watch

css:
	npx @tailwindcss/cli -i static/css/main.css -o static/css/output.css --minify

css-watch:
	npx @tailwindcss/cli -i static/css/main.css -o static/css/output.css --watch
