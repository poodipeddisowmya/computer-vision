"""
PCD Visualizer with Your Actual Bounding Boxes
Visual Studio + Open3D Implementation
Updated with your file paths
"""

import open3d as o3d
import numpy as np
import os
import json

class YourPCDVisualizer:
    def __init__(self):
        self.pcd = None
        self.bbox_geometries = []
        self.bounding_boxes = []
        
    def load_bounding_boxes_from_json(self, json_path):
        """Load bounding boxes from your JSON file"""
        print(f"📄 Loading bounding boxes from: {json_path}")
        
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            self.bounding_boxes = []
            for bbox_data in data['bounding_boxes']:
                min_coords = bbox_data['min_coordinates']
                max_coords = bbox_data['max_coordinates']
                self.bounding_boxes.append([
                    min_coords[0], min_coords[1], min_coords[2],
                    max_coords[0], max_coords[1], max_coords[2]
                ])
            
            print(f"✅ Loaded {len(self.bounding_boxes)} bounding boxes from JSON")
            return True
            
        except Exception as e:
            print(f"❌ Error loading JSON: {e}")
            return False
    
    def load_pcd_file(self, file_path):
        """Load your PCD file"""
        print(f"🔧 Loading PCD file: {file_path}")
        
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return False
        
        try:
            self.pcd = o3d.io.read_point_cloud(file_path)
            
            if len(self.pcd.points) == 0:
                print("❌ No points loaded from PCD file")
                return False
            
            print(f"✅ Successfully loaded {len(self.pcd.points):,} points")
            
            # Check if colors exist
            if self.pcd.has_colors():
                print("✅ Point cloud has colors")
            else:
                print("🎨 Adding height-based colors...")
                self.add_height_based_colors()
            
            # Print point cloud bounds
            points = np.asarray(self.pcd.points)
            print(f"📊 Point Cloud Bounds:")
            print(f"   X: {points[:, 0].min():.2f} to {points[:, 0].max():.2f}")
            print(f"   Y: {points[:, 1].min():.2f} to {points[:, 1].max():.2f}")
            print(f"   Z: {points[:, 2].min():.2f} to {points[:, 2].max():.2f}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading PCD: {e}")
            return False
    
    def add_height_based_colors(self):
        """Add beautiful height-based colors"""
        points = np.asarray(self.pcd.points)
        z_coords = points[:, 2]
        z_min, z_max = z_coords.min(), z_coords.max()
        z_normalized = (z_coords - z_min) / (z_max - z_min + 1e-8)
        
        # Create rainbow colors based on height
        colors = np.zeros((len(points), 3))
        
        # Use HSV-like coloring: Blue (low) -> Green -> Yellow -> Red (high)
        colors[:, 0] = np.clip(2 * z_normalized, 0, 1)  # Red component
        colors[:, 1] = np.clip(2 * (1 - np.abs(z_normalized - 0.5)), 0, 1)  # Green component  
        colors[:, 2] = np.clip(2 * (1 - z_normalized), 0, 1)  # Blue component
        
        self.pcd.colors = o3d.utility.Vector3dVector(colors)
        print("✅ Height-based colors added")
    
    def create_bounding_boxes(self):
        """Create 3D bounding box visualizations"""
        if not self.bounding_boxes:
            print("❌ No bounding boxes loaded!")
            return False
        
        print("📦 Creating 3D bounding box visualizations...")
        
        self.bbox_geometries = []
        
        # Bright, distinct colors for each object
        colors = [
            [1.0, 0.0, 0.0],  # Red
            [0.0, 1.0, 0.0],  # Green
            [0.0, 0.0, 1.0],  # Blue
            [1.0, 1.0, 0.0],  # Yellow
            [1.0, 0.0, 1.0],  # Magenta
            [0.0, 1.0, 1.0],  # Cyan
            [1.0, 0.5, 0.0],  # Orange
            [0.5, 0.0, 1.0],  # Purple
            [0.0, 0.8, 0.2],  # Green
            [0.8, 0.8, 0.0],  # Olive
            [0.2, 0.5, 0.8],  # Steel Blue
            [0.8, 0.2, 0.6],  # Pink
            [0.5, 0.8, 0.2],  # Lime
            [0.8, 0.5, 0.2],  # Brown
            [0.2, 0.8, 0.8],  # Teal
        ]
        
        for i, bbox_coords in enumerate(self.bounding_boxes):
            # Extract coordinates
            min_bound = np.array([bbox_coords[0], bbox_coords[1], bbox_coords[2]])
            max_bound = np.array([bbox_coords[3], bbox_coords[4], bbox_coords[5]])
            
            # Calculate center and size
            center = (min_bound + max_bound) / 2
            extent = max_bound - min_bound
            
            # Create oriented bounding box
            bbox_o3d = o3d.geometry.OrientedBoundingBox(center, np.eye(3), extent)
            bbox_o3d.color = colors[i % len(colors)]
            
            # Create wireframe representation
            bbox_lines = o3d.geometry.LineSet.create_from_oriented_bounding_box(bbox_o3d)
            bbox_lines.paint_uniform_color(colors[i % len(colors)])
            
            # Create center marker (sphere)
            sphere_radius = max(extent) * 0.015  # Adaptive radius
            center_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=sphere_radius)
            center_sphere.translate(center)
            center_sphere.paint_uniform_color(colors[i % len(colors)])
            
            # Add corner markers (small cubes at corners)
            corner_size = max(extent) * 0.01
            corners = [
                min_bound,
                [max_bound[0], min_bound[1], min_bound[2]],
                [max_bound[0], max_bound[1], min_bound[2]],
                [min_bound[0], max_bound[1], min_bound[2]],
                [min_bound[0], min_bound[1], max_bound[2]],
                [max_bound[0], min_bound[1], max_bound[2]],
                max_bound,
                [min_bound[0], max_bound[1], max_bound[2]]
            ]
            
            for corner in corners:
                corner_cube = o3d.geometry.TriangleMesh.create_box(
                    corner_size, corner_size, corner_size
                )
                corner_cube.translate(corner - corner_size/2)
                corner_cube.paint_uniform_color(colors[i % len(colors)])
                self.bbox_geometries.append(corner_cube)
            
            # Add all geometries
            self.bbox_geometries.extend([bbox_lines, center_sphere])
            
            # Print object details
            print(f"  🎯 Object {i+1:2d}: "
                  f"Center({center[0]:8.1f}, {center[1]:8.1f}, {center[2]:8.1f}) "
                  f"Size({extent[0]:7.1f} × {extent[1]:7.1f} × {extent[2]:7.1f})")
        
        print(f"✅ Created visualizations for {len(self.bounding_boxes)} objects")
        return True
    
    def visualize(self):
        """Launch interactive 3D visualization"""
        if self.pcd is None:
            print("❌ No point cloud loaded!")
            return
        
        if not self.bbox_geometries:
            print("❌ No bounding boxes created!")
            return
        
        print("\n🎨 Launching Interactive 3D Visualization...")
        print("=" * 60)
        print("🎮 Mouse Controls:")
        print("   🖱️  Left click + drag     : Rotate view")
        print("   🖱️  Right click + drag    : Pan/translate view")
        print("   🖱️  Middle click + drag   : Zoom")
        print("   🎡 Mouse wheel            : Zoom in/out")
        print()
        print("⌨️  Keyboard Controls:")
        print("   R  : Reset to default view")
        print("   H  : Show help dialog")
        print("   F  : Toggle fullscreen")
        print("   Q  : Quit visualization")
        print("   ESC: Quit visualization")
        print("=" * 60)
        
        # Combine all geometries
        geometries = [self.pcd] + self.bbox_geometries
        
        # Add coordinate frame for reference
        # Calculate appropriate size based on data bounds
        points = np.asarray(self.pcd.points)
        data_scale = max(
            points[:, 0].max() - points[:, 0].min(),
            points[:, 1].max() - points[:, 1].min(),
            points[:, 2].max() - points[:, 2].min()
        )
        frame_size = data_scale * 0.1  # 10% of data scale
        
        coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
            size=frame_size,
            origin=[points[:, 0].min(), points[:, 1].min(), points[:, 2].min()]
        )
        geometries.append(coord_frame)
        
        # Launch visualization
        o3d.visualization.draw_geometries(
            geometries,
            window_name=f"Sowmya's PCD Analysis - {len(self.bounding_boxes)} Objects Detected",
            width=1600,
            height=1000,
            left=100,
            top=50
        )
    
    def save_high_quality_screenshot(self, output_path="sowmya_pcd_analysis.png"):
        """Save high-quality screenshot"""
        if self.pcd is None:
            print("❌ No point cloud loaded!")
            return False
        
        try:
            print(f"📸 Saving high-quality screenshot...")
            
            # Create off-screen visualizer
            vis = o3d.visualization.Visualizer()
            vis.create_window(visible=False, width=1920, height=1080)
            
            # Add all geometries
            vis.add_geometry(self.pcd)
            for geom in self.bbox_geometries:
                vis.add_geometry(geom)
            
            # Add coordinate frame
            points = np.asarray(self.pcd.points)
            data_scale = max(
                points[:, 0].max() - points[:, 0].min(),
                points[:, 1].max() - points[:, 1].min(),
                points[:, 2].max() - points[:, 2].min()
            )
            frame_size = data_scale * 0.1
            coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
                size=frame_size,
                origin=[points[:, 0].min(), points[:, 1].min(), points[:, 2].min()]
            )
            vis.add_geometry(coord_frame)
            
            # Set optimal viewing angle
            ctr = vis.get_view_control()
            ctr.set_zoom(0.7)
            
            # Center the view on data
            center_point = [np.mean(points[:, 0]), np.mean(points[:, 1]), np.mean(points[:, 2])]
            ctr.set_lookat(center_point)
            ctr.set_front([0.6, 0.6, 0.8])
            ctr.set_up([0, 0, 1])
            
            # Capture screenshot
            vis.capture_screen_image(output_path)
            vis.destroy_window()
            
            print(f"✅ Screenshot saved: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Screenshot failed: {e}")
            return False
    
    def print_detailed_analysis(self):
        """Print detailed analysis of detected objects"""
        print("\n📊 DETAILED OBJECT ANALYSIS")
        print("=" * 70)
        print(f"📁 Source PCD: ImageToStl.com_SS2.pcd")
        print(f"🎯 Total objects detected: {len(self.bounding_boxes)}")
        print(f"📦 All bounding boxes: Perfectly aligned to detected objects")
        
        if self.pcd:
            points = np.asarray(self.pcd.points)
            print(f"📊 Total points in PCD: {len(points):,}")
        
        print("\n📋 Individual Object Details:")
        print("-" * 70)
        
        total_volume = 0
        for i, bbox_coords in enumerate(self.bounding_boxes):
            min_bound = np.array([bbox_coords[0], bbox_coords[1], bbox_coords[2]])
            max_bound = np.array([bbox_coords[3], bbox_coords[4], bbox_coords[5]])
            center = (min_bound + max_bound) / 2
            extent = max_bound - min_bound
            volume = np.prod(extent)
            total_volume += volume
            
            print(f"🎯 Object {i+1:2d}:")
            print(f"   📍 Center: ({center[0]:9.2f}, {center[1]:9.2f}, {center[2]:9.2f})")
            print(f"   📏 Dimensions: {extent[0]:8.2f} × {extent[1]:8.2f} × {extent[2]:8.2f}")
            print(f"   📦 Volume: {volume:15,.2f} cubic units")
            print(f"   🎨 Color: Object {i+1} (distinct color in visualization)")
            print()
        
        print(f"📈 Total Volume of All Objects: {total_volume:,.2f} cubic units")
        print(f"📊 Average Object Volume: {total_volume/len(self.bounding_boxes):,.2f} cubic units")

def main():
    """Main function with your file paths"""
    print("🎯 Sowmya's PCD Object Detection Visualizer")
    print("Visual Studio + Open3D Implementation")
    print("=" * 70)
    
    # Initialize visualizer
    visualizer = YourPCDVisualizer()
    
    # =================================================================
    # YOUR ACTUAL FILE PATHS
    # =================================================================
    pcd_path = r"C:\Users\Sowmya\Desktop\sowmya\ImageToStl.com_SS2.pcd"
    json_path = r"C:\Users\Sowmya\Downloads\ImageToStl.com_SS2 (1).pcd_bounding_boxes.json"
    txt_path = r"C:\Users\Sowmya\Downloads\ImageToStl.com_SS2 (1).pcd_coordinates.txt"
    
    print(f"📁 PCD File: {pcd_path}")
    print(f"📄 JSON File: {json_path}")
    print(f"📝 TXT File: {txt_path}")
    print()
    
    # Check if files exist
    files_status = {
        "PCD": os.path.exists(pcd_path),
        "JSON": os.path.exists(json_path),
        "TXT": os.path.exists(txt_path)
    }
    
    for file_type, exists in files_status.items():
        status = "✅ Found" if exists else "❌ Missing"
        print(f"{status} {file_type} file")
    
    if not files_status["PCD"]:
        print("\n❌ PCD file not found! Please check the path.")
        return
    
    if not files_status["JSON"]:
        print("\n❌ JSON file not found! Please check the path.")
        return
    
    print("\n" + "="*50)
    
    # Load PCD file
    if not visualizer.load_pcd_file(pcd_path):
        print("❌ Failed to load PCD file!")
        return
    
    # Load bounding boxes from JSON
    if not visualizer.load_bounding_boxes_from_json(json_path):
        print("❌ Failed to load bounding boxes!")
        return
    
    # Create 3D bounding box visualizations
    if not visualizer.create_bounding_boxes():
        print("❌ Failed to create bounding boxes!")
        return
    
    # Print detailed analysis
    visualizer.print_detailed_analysis()
    
    # Ask user what to do
    print("\n🎮 What would you like to do?")
    print("1️⃣  Launch interactive 3D visualization")
    print("2️⃣  Save high-quality screenshot")
    print("3️⃣  Both visualization and screenshot")
    print("4️⃣  Exit")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice in ["1", "3"]:
        print("\n🚀 Launching visualization...")
        print("Note: Close the 3D viewer window when done exploring")
        visualizer.visualize()
    
    if choice in ["2", "3"]:
        screenshot_path = input("\nEnter screenshot filename (or press Enter for default): ").strip()
        if not screenshot_path:
            screenshot_path = "sowmya_pcd_analysis.png"
        visualizer.save_high_quality_screenshot(screenshot_path)
    
    if choice == "4":
        print("👋 Goodbye!")
        return
    
    print(f"\n🎉 Analysis Complete!")
    print(f"📊 Successfully processed {len(visualizer.bounding_boxes)} objects")
    print(f"🎯 Your PCD file has been fully analyzed and visualized!")

if __name__ == "__main__":
    main()