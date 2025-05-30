import open3d as o3d
import numpy as np

def load_pcd(file_path):
    """Load a PCD file using Open3D."""
    pcd = o3d.io.read_point_cloud(file_path)
    return pcd

def pick_points(pcd):
    """Allow the user to pick points from the visualized point cloud."""
    print("Pick at least two points to compute the diameter and press 'Q' when done.")
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window()
    vis.add_geometry(pcd)
    vis.run()  # Blocks execution until user selects points
    vis.destroy_window()
    return vis.get_picked_points()

def compute_diameter(pcd, selected_indices):
    """Compute the diameter based on the farthest distance between selected points."""
    points = np.asarray(pcd.points)
    selected_points = points[selected_indices]
    
    if len(selected_points) < 2:
        print("Please select at least two points.")
        return None
    
    # Compute pairwise distances
    from scipy.spatial.distance import pdist
    distances = pdist(selected_points, metric='euclidean')
    diameter = np.max(distances)  # Maximum distance between any two points
    return diameter

def visualize_pcd(pcd):
    """Visualize the point cloud."""
    o3d.visualization.draw_geometries([pcd])

# Define file path
pcd_path = r"C:\Users\Sowmya\OneDrive\Desktop\SHARMA\M3 UTENSIL.pcd"

# Load the point cloud
pcd = load_pcd(pcd_path)
visualize_pcd(pcd)

# Allow user to pick points
selected_indices = pick_points(pcd)

# Compute and display diameter
if selected_indices:
    diameter = compute_diameter(pcd, selected_indices)
    if diameter is not None:
        print(f"Computed diameter: {diameter:.4f}")


