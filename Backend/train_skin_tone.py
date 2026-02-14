'''
train_skin_tone.py - Shortcut that runs compute_centroids.py.

To recalculate skin tone reference values from the dataset, just run:
    python compute_centroids.py
'''

# Runs compute_centroids so this file still works as an entry point.
from compute_centroids import main

if __name__ == "__main__":
    main()
