import csv
import heapq
import os


def csv_reader_with_name(filename):
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def incremental_merge_sort(input_files, output_file):
    fieldnames = ['uuid', 'time', 'mcc', 'mnc', 'area_code', 'cell_id']

    with open(output_file, 'w', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        # Create a list of iterators
        iterators = []
        for filename in input_files:
            if os.path.exists(filename):
                iterator = csv_reader_with_name(filename)
                iterators.append(iterator)
            else:
                print(f"Warning: {filename} not found. Skipping.")

        # Initialize the heap with the first row from each iterator
        heap = []
        for i, iterator in enumerate(iterators):
            try:
                row = next(iterator)
                heapq.heappush(heap, (float(row['time']), i, row))
            except StopIteration:
                pass

        # Merge sort
        while heap:
            _, i, row = heapq.heappop(heap)
            writer.writerow(row)

            try:
                next_row = next(iterators[i])
                heapq.heappush(heap, (float(next_row['time']), i, next_row))
            except StopIteration:
                pass


if __name__ == '__main__':
    # List of input CSV files
    input_files = [
        'gv-data/synthetic/synthetic.csv',
        'gv-data/synthetic/synthetic_reversal.csv',
        # Add more file names as needed
    ]

    output_file = 'gv-data/synthetic/all_synthetic.csv'
    incremental_merge_sort(input_files, output_file)
    print(f"Combined and sorted data written to {output_file}")
