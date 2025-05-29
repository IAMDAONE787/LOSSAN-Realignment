#!/bin/bash

# Install necessary system libraries for Shapely
apt-get update && apt-get install -y libgeos-dev

echo "Setup completed." 