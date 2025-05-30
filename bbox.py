import open3d as o3d
import numpy as np

def load_pcd(file_path):
    """Load a PCD file using Open3D."""
    pcd = o3d.io.read_point_cloud(file_path)
    return pcd

def extract_roi(pcd, xyz, dxdydz):
    """Extract a region of interest (ROI) from the point cloud with precise filtering.
    The input dimensions are assumed to be in the same unit as the PCD (no conversion)."""
    center = np.array(xyz)
    half_size = np.array(dxdydz) / 2  # Get half-lengths
    
    points = np.asarray(pcd.points)
    points = np.maximum(points, 0)  # Ensure all values are positive
    
    print(f"Total points in PCD: {len(points)}")
    print(f"Center: {xyz}")
    print(f"Dimensions: {dxdydz}")
    
    mask_x = np.logical_and(points[:, 0] >= center[0] - half_size[0], points[:, 0] <= center[0] + half_size[0])
    mask_y = np.logical_and(points[:, 1] >= center[1] - half_size[1], points[:, 1] <= center[1] + half_size[1])
    mask_z = np.logical_and(points[:, 2] >= center[2] - half_size[2], points[:, 2] <= center[2] + half_size[2])
    
    mask = np.logical_and.reduce((mask_x, mask_y, mask_z))
    indices = np.where(mask)[0]
    
    print(f"Points in extracted ROI: {len(indices)}")
    
    extracted_pcd = pcd.select_by_index(indices)
    return extracted_pcd

def pick_points(pcd):
    """Visualize the point cloud and allow point selection."""
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window()
    vis.add_geometry(pcd)
    vis.run()
    vis.destroy_window()
    
    picked_points = vis.get_picked_points()
    picked_coords = np.asarray(pcd.points)[picked_points]
    
    picked_coords = np.maximum(picked_coords, 0)  # Ensure positive values
    ImageToStl.com_SS2.pcd
    print("Selected Points' Coordinates:")
    for i, coord in enumerate(picked_coords):
        print(f"Point {i + 1}: {coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f}")
    
    return picked_coords

def calculate_distance(picked_coords):
    """Calculate and display the distance between two selected points."""
    if len(picked_coords) != 2:
        print("Please select exactly two points to calculate the distance.")
        return
    
    distance = np.linalg.norm(picked_coords[0] - picked_coords[1])
    print(f"Distance between selected points: {distance:.2f} units")

def draw_bounding_box(picked_coords):
    """Draw a bounding box based on selected points."""
    if len(picked_coords) < 8:
        print("At least 8 points are required to form a bounding box.")
        return None
    
    aabb = o3d.geometry.AxisAlignedBoundingBox.create_from_points(o3d.utility.Vector3dVector(picked_coords))
    aabb.color = (1, 0, 0)  # Red bounding box
    return aabb

# Define file path
pcd_path = r"C:\Users\Sowmya\OneDrive\Desktop\SHARMA\M3 UTENSIL.pcd"

# Load the point cloud
pcd = load_pcd(pcd_path)

# Visualize the full PCD and allow point selection
print("Select points from the full point cloud to determine min/max values.")
selected_coords_full = pick_points(pcd)
if len(selected_coords_full) > 0:
    min_values = np.min(selected_coords_full, axis=0)
    max_values = np.max(selected_coords_full, axis=0)
    print(f"Min values: {min_values}")
    print(f"Max values: {max_values}")

# Get user input for center and dimensions
xyz = list(map(float, input("Enter the center (x y z): ").split()))
dxdydz = list(map(float, input("Enter the dimensions (dx dy dz): ").split()))

# Extract and visualize the ROI
roi_pcd = extract_roi(pcd, xyz, dxdydz)
if len(np.asarray(roi_pcd.points)) > 0:
    print("Select points from the extracted object to find distances or draw bounding boxes.")
    picked_coords = pick_points(roi_pcd)
    if len(picked_coords) >= 8:
        bbox = draw_bounding_box(picked_coords)
        if bbox:
            o3d.visualization.draw_geometries([roi_pcd, bbox])
    elif len(picked_coords) == 2:
        calculate_distance(picked_coords)











