clean:
	rm -rf ./outputs/

clean-build:
	rm -rf ./build/ && rm -rf ./dist/

download-model:
	python3 scripts/download_model.py

build-binary:
	python3 scripts/build_binary.py --clean

test:
	python3 -m unittest discover -s tests -v
