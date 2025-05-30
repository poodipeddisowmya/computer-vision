import open3d as o3d
import numpy as np

def main():
    # Hardcoded file path
    pcd_path = r"C:\Users\Sowmya\Desktop\sowmya\NEW ASSEMBLY 3.pcd"

    # Load point cloud
    pcd = o3d.io.read_point_cloud(pcd_path)

    # Predefined values
    diameter = 102.41582171982662
    center_utensil = np.array([280.20007324, 53.1825161, 56.29000235])
    green_point_count = 703
    center_handle = np.array([225.53120928, 53.16391481, 50.71249868])
    orientation_vector = np.array([0.99554083, -0.00109202, 0.09432529])

    # Print values
    print(f"Computed Diameter: {diameter}")
    print(f"Center of Utensil: {center_utensil}")
    print(f"Number of detected green points: {green_point_count}")
    print(f"Handle Center: {center_handle}")
    print(f"Orientation Vector: {orientation_vector}")

    # Create blue sphere at handle center
    handle_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=5)
    handle_sphere.paint_uniform_color([0, 0, 1])
    handle_sphere.translate(center_handle)

    # Create red sphere at utensil center
    utensil_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=5)
    utensil_sphere.paint_uniform_color([1, 0, 0])
    utensil_sphere.translate(center_utensil)

    # Create orientation arrow
    arrow = o3d.geometry.TriangleMesh.create_arrow(
        cylinder_radius=1, cone_radius=2, cylinder_height=50, cone_height=10
    )
    arrow.paint_uniform_color([1, 0, 0])  # Red arrow

    # Compute rotation to align arrow with orientation vector
    z_axis = np.array([0, 0, 1])
    rotation_axis = np.cross(z_axis, orientation_vector)
    rotation_angle = np.arccos(np.dot(z_axis, orientation_vector) / (
        np.linalg.norm(z_axis) * np.linalg.norm(orientation_vector)
    ))

    if np.linalg.norm(rotation_axis) > 1e-6:
        rotation_axis /= np.linalg.norm(rotation_axis)
        R = o3d.geometry.get_rotation_matrix_from_axis_angle(rotation_axis * rotation_angle)
        arrow.rotate(R, center=(0, 0, 0))

    # Position arrow at handle center
    arrow.translate(center_handle)

    # Visualize everything
    o3d.visualization.draw_geometries([pcd, handle_sphere, utensil_sphere, arrow])

if _name_ == "_main_":
    main()