# 🚀 Rubric Editing - Quick Start Guide

**Status**: ✅ Fully Functional  
**Last Updated**: October 14, 2025

---

## 📍 Access the Editor

1. **Login**: http://localhost:5173
   - Email: `admin@owi.com`
   - Password: `admin`

2. **Navigate**: Click "Evaluaitor" in the navigation bar

3. **Create or Edit**:
   - **Create New**: Click "Create Rubric" button
   - **Edit Existing**: Click "Edit" button on any rubric in the list

---

## ✏️ Editing Your Rubric

### Edit Metadata
Click on any of these fields to edit:
- **Title** ⭐ Required
- **Description** ⭐ Required  
- **Subject** ⭐ Required (dropdown)
- **Grade Level** ⭐ Required (dropdown)

### Edit Table Cells
**ALL cells are editable!** Just click any cell:

#### Criterion Column (left)
- **Criterion Name**: Click to edit the criterion title
- **Criterion Description**: Click to edit what this criterion assesses
- **Weight**: Click to edit the percentage weight (0-100)

#### Performance Level Columns
- **Each cell**: Click to edit the description for that performance level
- **Example**: Click "Good understanding demonstrated" to edit that level description

### Saving Your Edits

#### Save Individual Cells
- **For text inputs**: Press `Enter` to save, `Esc` to cancel
- **For textareas**: Press `Ctrl+Enter` (or `Cmd+Enter` on Mac) to save, `Esc` to cancel
- **Alternative**: Click outside the cell to auto-save

#### Save Entire Rubric
- Click the **"Update Rubric"** button in the header
- Wait for "Rubric saved successfully" message
- Changes are now in the database! ✅

---

## 🎨 Visual Cues

### Edit Mode
- **Blue "Editing" button** = Edit mode active
- **Gray "View Only" button** = View mode (read-only)
- Click to toggle between modes

### Active Editor
- **Blue border** around the cell you're editing
- **Placeholder text** with keyboard shortcuts
- **Blue hover effect** on editable cells

### Buttons
- **Update Rubric** = Save all changes to backend
- **Save as New Version** = Create a copy with your changes
- **Undo** = Revert last change (only in edit mode)
- **Redo** = Restore undone change (only in edit mode)

---

## ⌨️ Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Save text input | `Enter` |
| Save textarea | `Ctrl+Enter` (or `Cmd+Enter`) |
| Cancel edit | `Esc` |
| New line in textarea | `Enter` (without Ctrl) |
| Navigate cells | `Tab` / `Shift+Tab` |

---

## 📝 Example Workflow

### Editing Multiple Cells
1. Click "Edit" on your rubric
2. Click "Student demonstrates understanding" (criterion description)
3. Type your changes
4. Click outside or press Ctrl+Enter
5. Click "Good understanding demonstrated" (level cell)
6. Type your changes
7. Click outside or press Ctrl+Enter
8. Repeat for any other cells you want to edit
9. Click "Update Rubric" button
10. Done! All changes saved ✅

### Adding Criteria or Levels
- **Add Criterion**: Click "Add Criterion" button (adds a new row)
- **Add Level**: Click "Add Level" button (adds a new column to all criteria)
- **Remove**: Click the trash icon next to criterion or level

---

## ✅ What Works

✅ **All cells editable** - Criterion name, description, weight, and ALL level descriptions  
✅ **No ghost editors** - Only one editor appears where you click  
✅ **Changes persist** - Saves to database and reloads correctly  
✅ **Undo/Redo** - Track your changes and revert if needed  
✅ **Keyboard shortcuts** - Efficient editing workflow  
✅ **Visual feedback** - Clear indication of what you're editing  

---

## 🐛 Troubleshooting

### Cell won't open for editing
- ✅ Check that you're in **Edit mode** (should see "Editing" button, not "View Only")
- ✅ Click the toggle to switch to edit mode

### Changes not saving
- ✅ Make sure to click **"Update Rubric"** button after editing cells
- ✅ Look for "Rubric saved successfully" in console (F12 to open)
- ✅ Check that you're logged in (see your name in top right)

### Ghost editor appearing
- ✅ This has been fixed! Should not happen anymore
- ✅ If you see one, refresh the page to get latest code

### Backend errors
- ✅ Check docker containers are running: `docker ps`
- ✅ Restart backend: `docker restart lamb-backend`
- ✅ Check logs: `docker logs lamb-backend --tail 50`

---

## 🧪 Test Your Installation

Run the automated test script:
```bash
./testing/test_rubric_edit_flow.sh
```

Expected output:
```
✅ Login successful
✅ Rubric created successfully
✅ Rubric fetched successfully  
✅ Rubric updated successfully
✅ Update verified!
✅ TEST COMPLETED!
```

---

## 📞 Support

- **Documentation**: See `Documentation/evaluaitor.md` for full details
- **Issues**: Report via GitHub issues
- **Demo**: http://localhost:5173/evaluaitor

---

**Happy Rubric Editing! 🎉**

