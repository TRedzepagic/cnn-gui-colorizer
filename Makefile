clean:
	rm -rf ./colorizedFrames/ && rm -rf ./colorizedImages/ && rm -rf ./colorizedVideos

clean-build:
	rm -rf ./build/ && rm -rf ./dist/

download-model:
	python3 scripts/download_model.py

build-binary:
	python3 scripts/build_binary.py --clean

test:
	python3 -m unittest discover -s tests -v
