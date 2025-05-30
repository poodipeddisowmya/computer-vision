import open3d as o3d
import numpy as np
from collections import defaultdict
from sklearn.cluster import DBSCAN

def process_point_cloud(pcd_file, z_threshold, interval, xy_tolerance):
    # Load the point cloud
    pcd = o3d.io.read_point_cloud(pcd_file)
    points = np.asarray(pcd.points)

    # Dictionary to store points with similar x, y coordinates
    xy_dict = defaultdict(list)

    # Function to round x, y values based on tolerance
    def round_xy(x, y, tolerance):
        return (round(x / tolerance) * tolerance, round(y / tolerance) * tolerance)

    # Scan through all points and group them by similar x, y coordinates
    for point in points:
        x, y, z = point
        rounded_xy = round_xy(x, y, xy_tolerance)  # Round x, y based on tolerance
        xy_dict[rounded_xy].append(z)  # Store the z value

    # List to store the new points
    new_points = []

    # Iterate through the dictionary to find points with similar x, y but different z
    for xy_key, z_values in xy_dict.items():
        if len(z_values) > 1:  # More than one z value for similar x, y
            z_values_sorted = sorted(z_values)
            for i in range(len(z_values_sorted) - 1):
                z_diff = z_values_sorted[i + 1] - z_values_sorted[i]
                if z_diff > z_threshold:
                    # Add extra points at regular intervals along z
                    num_intervals = int(z_diff / interval)
                    for j in range(1, num_intervals + 1):
                        new_z = z_values_sorted[i] + j * interval
                        new_points.append([xy_key[0], xy_key[1], new_z])  # Use rounded x, y

    # Combine the original points with the new points
    all_points = np.vstack([points, np.array(new_points)])

    # Create a new point cloud with the combined points
    new_pcd = o3d.geometry.PointCloud()
    new_pcd.points = o3d.utility.Vector3dVector(all_points)

    # Save the new point cloud to a file
    o3d.io.write_point_cloud("processed_point_cloud.pcd", new_pcd)

    print(f"Processed point cloud saved as 'processed_point_cloud.pcd'")
    print(f"Added {len(new_points)} new points.")

    return new_pcd

def cluster_and_draw_bounding_boxes(pcd, eps, min_samples=10):
    """
    Clusters the point cloud using DBSCAN and draws bounding boxes for each cluster.
    """
    points = np.asarray(pcd.points)

    # Perform DBSCAN clustering
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(points)
    labels = db.labels_

    # Get unique labels (clusters), ignoring noise (-1)
    unique_labels = set(labels) - {-1}

    # Create a list to hold all geometries for visualization
    geometries = []

    for label in unique_labels:
        # Extract points belonging to the current cluster
        cluster_points = points[labels == label]

        # Create a point cloud for the cluster
        cluster_pcd = o3d.geometry.PointCloud()
        cluster_pcd.points = o3d.utility.Vector3dVector(cluster_points)

        # Compute the oriented bounding box (OBB) for the cluster
        obb = cluster_pcd.get_oriented_bounding_box()
        obb.color = (0, 1, 0)  # Green color for the bounding box

        # Add the point cloud and bounding box to the geometries list
        geometries.append(cluster_pcd)
        geometries.append(obb)

    # Visualize all clusters and their bounding boxes
    o3d.visualization.draw_geometries(geometries, window_name="Clusters with Bounding Boxes")

# Example usage
pcd_file = r"C:\Users\Sowmya\Desktop\sowmya\uncommon_points.pcd"  # Replace with your PCD file path
z_threshold = 0.5  # Threshold for the difference in z values
interval = 0.1  # Interval for adding new points along z
xy_tolerance = 0.1  # Tolerance for x, y values (points within this range are considered the same)

# Process the point cloud
processed_pcd = process_point_cloud(pcd_file, z_threshold, interval, xy_tolerance)

# Cluster the processed point cloud and draw bounding boxes
cluster_and_draw_bounding_boxes(processed_pcd, eps=0.5, min_samples=10)
