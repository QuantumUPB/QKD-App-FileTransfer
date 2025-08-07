.PHONY: zip broker

zip:
	zip -r qotp.zip . -x qotp.zip -x '.git/*'

broker:
	docker-compose up -d --build broker

