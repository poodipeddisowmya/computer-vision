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
    """Allows user to select points from the extracted part."""
    print("Please select points in the visualization and press Q to finish.")
    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window()
    vis.add_geometry(pcd)
    vis.run()  # User selects points
    vis.destroy_window()
    
    selected_indices = vis.get_picked_points()
    print(f"Selected {len(selected_indices)} points.")
    
    if not selected_indices:
        print("No points selected.")
        return None
    
    return pcd.select_by_index(selected_indices)

def compute_length_depth(pcd):
    """Compute the length and depth of the selected points from the extracted part."""
    points = np.asarray(pcd.points)
    if len(points) == 0:
        print("No points available for length and depth computation.")
        return None, None, None
    
    min_x, max_x = np.min(points[:, 0]), np.max(points[:, 0])
    min_z, max_z = np.min(points[:, 2]), np.max(points[:, 2])
    length = max_x - min_x  # Length along x-axis
    depth = max_z - min_z    # Depth along z-axis
    
    print(f"Selected Object Length (X-axis): {length}")
    print(f"Selected Object Depth (Z-axis): {depth}")
    
    # Create lines for visualization
    lines = [
        [[min_x, 0, min_z], [max_x, 0, min_z]],  # Length indicator
        [[min_x, 0, min_z], [min_x, 0, max_z]]   # Depth indicator
    ]
    
    line_set = o3d.geometry.LineSet()
    line_set.points = o3d.utility.Vector3dVector([point for line in lines for point in line])
    line_set.lines = o3d.utility.Vector2iVector([[0, 1], [2, 3]])
    
    return length, depth, line_set

def visualize_pcd(pcd, line_set=None):
    """Visualize the selected point cloud with optional length and depth indicators."""
    if len(np.asarray(pcd.points)) == 0:
        print("No points selected for visualization.")
        return
    objects = [pcd]
    if line_set:
        objects.append(line_set)
    o3d.visualization.draw_geometries(objects)

# Define file path
pcd_path = r"C:\Users\Sowmya\Desktop\sowmya\ImageToStl.com_SS2.pcd"

# Load the point cloud
pcd = load_pcd(pcd_path)

# Get user input for center and dimensions
xyz = list(map(float, input("Enter the center (x y z): ").split()))
dxdydz = list(map(float, input("Enter the dimensions (dx dy dz): ").split()))

# Extract and visualize the ROI
roi_pcd = extract_roi(pcd, xyz, dxdydz)

# Select points interactively from the extracted part
selected_pcd = pick_points(roi_pcd)

if selected_pcd:
    # Compute length and depth of the selected points
    length, depth, line_set = compute_length_depth(selected_pcd)
    
    # Visualize selected points with indicators
    visualize_pcd(selected_pcd, line_set)












