import open3d as o3d
import numpy as np

# **Step 1: Load the PCD file**
pcd = o3d.io.read_point_cloud(r"C:/Users/Sowmya/OneDrive/Desktop/SHARMA/ImageToStl.com_SS2.pcd")

print(f"Loaded point cloud with {len(pcd.points)} points")

# Visualize the original point cloud
o3d.visualization.draw_geometries([pcd], window_name="Original Point Cloud")

# **Step 2: Preprocessing (Downsampling & Noise Removal)**

# Voxel Downsampling (reduces density for efficiency)
pcd_downsampled = pcd.voxel_down_sample(voxel_size=0.02)  # Adjust voxel_size if needed

# Remove Statistical Outliers (removes noise)
cl, ind = pcd_downsampled.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
pcd_filtered = pcd_downsampled.select_by_index(ind)

# Visualize the cleaned point cloud
o3d.visualization.draw_geometries([pcd_filtered], window_name="Filtered Point Cloud")

print(f"Filtered point cloud contains {len(pcd_filtered.points)} points")

# **Step 3: Plane Segmentation using RANSAC**
plane_model, inliers = pcd_filtered.segment_plane(distance_threshold=0.02, ransac_n=3, num_iterations=1000)

# Extract plane (background) and objects (foreground)
plane = pcd_filtered.select_by_index(inliers)  # Ground/plane
objects = pcd_filtered.select_by_index(inliers, invert=True)  # Objects of interest

# Color plane & objects for visualization
plane.paint_uniform_color([1, 0, 0])  # Red for plane
objects.paint_uniform_color([0, 1, 0])  # Green for objects

# Visualize segmented objects and plane
o3d.visualization.draw_geometries([plane, objects], window_name="Segmented Plane & Objects")

print(f"Plane contains {len(plane.points)} points, objects contain {len(objects.points)} points")

# Save segmented objects (optional)
o3d.io.write_point_cloud("segmented_objects.pcd", objects)

# **Step 4: Clustering objects using DBSCAN**
labels = np.array(objects.cluster_dbscan(eps=20, min_points=500, print_progress=True))  # Adjust eps as needed

# Get the number of clusters (excluding noise points, which are labeled -1)
max_label = labels.max()
print(f"Found {max_label + 1} clusters")

# Assign random colors to clusters
colors = np.random.uniform(0, 1, size=(max_label + 1, 3))
cluster_sizes = {}

# Apply colors and count points in each cluster
clustered_objects = []
for i in range(max_label + 1):
    cluster_i = objects.select_by_index(np.where(labels == i)[0])
    cluster_sizes[i] = len(cluster_i.points)
    clustered_objects.append(cluster_i)
    o3d.io.write_point_cloud(f"object_{i}.pcd", cluster_i)
    print(f"Cluster {i} contains {len(cluster_i.points)} points")

# Assign colors to clusters (ignore noise points)
colored_labels = [colors[label] if label != -1 else [0, 0, 0] for label in labels]
objects.colors = o3d.utility.Vector3dVector(colored_labels)

# Define bounding box coordinates
base_coords = [
    [24, 59, 24],
    [324, 59, 24],
    [324, 59, 324],
    [24, 59, 324]
]

top_coords = [
    [24, 232, 24],
    [324, 232, 24],
    [324, 232, 324],
    [24, 232, 324]
]

shelf2_coords = [
    [24, 346, 24],
    [324, 346, 24],
    [324, 346, 324],
    [24, 346, 324]
]

shelf3_coords = [
    [24, 444, 24],
    [324, 444, 24],
    [324, 444, 324],
    [24, 444, 324]
]

# Function to create bounding boxes
def create_bounding_box_from_corners(corner_points, color=[1, 0, 0]):
    corner_array = np.array(corner_points)
    bbox = o3d.geometry.AxisAlignedBoundingBox.create_from_points(o3d.utility.Vector3dVector(corner_array))
    bbox.color = color
    return bbox
# Create bounding boxes
bbox_corners = base_coords + top_coords
bbox_corners_shelf2 = top_coords + shelf2_coords
bbox_corners_shelf3 = shelf2_coords + shelf3_coords

bb1 = create_bounding_box_from_corners(bbox)



