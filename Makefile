compile: src/arctic_spa/proto/arctic_spa_pb2.py

proto_out=src/arctic_spa/proto

$(proto_out):
	mkdir -p $@

$(proto_out)/arctic_spa_pb2.py: src/arctic_spa.proto $(proto_out)
	protoc --python_out=$(proto_out) -Isrc $<

clean:
	rm -rf $(proto_out)
	rm -rf dist/
