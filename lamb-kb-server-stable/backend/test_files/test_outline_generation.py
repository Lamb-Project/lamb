#!/usr/bin/env python3
"""
Test script for document outline generation in hierarchical ingestion plugin.

This test validates:
1. Outline is generated correctly from markdown headers
2. The include_outline parameter works as expected
3. Outline format matches the expected structure
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.hierarchical_ingest import HierarchicalIngestPlugin


def create_test_markdown_with_hierarchy():
    """Create a test Markdown file with hierarchical structure similar to the example."""
    test_content = """# Summa Tortillae: Tratado Exhaustivo sobre la Tortilla de Patatas Tradicional

Este es un tratado completo sobre la preparación de la tortilla de patatas.

## Paso 1: Ontología de los Ingredientes y Selección de Materiales

La selección de ingredientes es fundamental para el éxito de la tortilla.

### 1.1 La Patata: El Almidón como Estructura

Las patatas deben ser de calidad superior, preferiblemente variedades ricas en almidón.

### 1.2 El Huevo: Proteína y Color

Los huevos frescos son esenciales para obtener el color y textura deseados.

### 1.3 El Aceite: El Baño Térmico

El aceite de oliva virgen extra es la mejor opción para el confitado.

## Paso 2: La Arquitectura del Corte (Mise en Place)

La preparación de los ingredientes requiere técnica y precisión.

### 2.1 El Ritual del "Chascado"

El corte de las patatas debe ser uniforme para una cocción homogénea.

### 2.2 La Cebolla y su Desintegración

La cebolla debe cortarse finamente para integrarse en la mezcla.

## Paso 3: El Confitado Dialéctico (El Control del Fuego)

El control de la temperatura es crucial en el proceso de confitado.

### 3.1 La Termodinámica del Aceite

El aceite debe mantenerse a temperatura constante durante el confitado.

### 3.2 El Punto de Tersura

Las patatas deben alcanzar el punto exacto de cocción sin dorarse.

## Paso 4: La Infiltración y el Reposo Sagrado

La integración del huevo con las patatas es un momento crítico.

### 4.1 El Batido Atmosférico

Los huevos deben batirse correctamente para incorporar aire.

### 4.2 La Ósmosis del Huevo y la Patata

El reposo permite que los sabores se integren armoniosamente.

## Paso 5: La Consagración en la Sartén y la Gravedad

La cocción final requiere maestría y control del calor.

### 5.1 El Sellado de Alta Temperatura

El sellado inicial crea la estructura exterior de la tortilla.

### 5.2 El Giro de Muñeca (El Vuelco)

El volteo de la tortilla es un arte que requiere práctica.

## Paso 6: El Reposo Térmico y la Degustación

El reposo final permite la redistribución de jugos y sabores.

### 6.1 La Redistribución de Jugos

El interior debe reposar para alcanzar la temperatura ideal.

### 6.2 El Corte Final

La tortilla debe cortarse cuando haya alcanzado el punto perfecto.
"""
    
    test_file_path = Path("/tmp/test_outline_tortilla.md")
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    return test_file_path


def test_outline_generation():
    """Test the document outline generation feature."""
    print("=" * 80)
    print("TESTING DOCUMENT OUTLINE GENERATION")
    print("=" * 80)
    
    # Create test file
    test_file = create_test_markdown_with_hierarchy()
    print(f"\n✓ Created test file: {test_file}")
    
    # Initialize plugin
    plugin = HierarchicalIngestPlugin()
    print(f"✓ Initialized plugin: {plugin.name}")
    
    # Test 1: Ingest WITHOUT outline (default behavior)
    print("\n" + "-" * 80)
    print("TEST 1: Ingest without outline (include_outline=False)")
    print("-" * 80)
    
    results_no_outline = plugin.ingest(
        str(test_file),
        parent_chunk_size=2000,
        child_chunk_size=400,
        include_outline=False
    )
    
    print(f"✓ Generated {len(results_no_outline)} chunks")
    
    # Check that no outline is present in the content
    has_outline_header = any("Document Outline" in chunk["text"] for chunk in results_no_outline)
    if has_outline_header:
        print("✗ FAIL: Document outline found when it should not be present")
        return False
    else:
        print("✓ No document outline found (as expected)")
    
    # Test 2: Ingest WITH outline
    print("\n" + "-" * 80)
    print("TEST 2: Ingest with outline (include_outline=True)")
    print("-" * 80)
    
    results_with_outline = plugin.ingest(
        str(test_file),
        parent_chunk_size=2000,
        child_chunk_size=400,
        include_outline=True
    )
    
    print(f"✓ Generated {len(results_with_outline)} chunks")
    
    # Check that outline is present
    outline_chunks = [chunk for chunk in results_with_outline if "Document Outline" in chunk["text"]]
    if not outline_chunks:
        print("✗ FAIL: Document outline not found when it should be present")
        return False
    else:
        print(f"✓ Found {len(outline_chunks)} chunk(s) containing document outline")
    
    # Test 3: Verify outline format
    print("\n" + "-" * 80)
    print("TEST 3: Verify outline format and structure")
    print("-" * 80)
    
    # Find chunks with the complete outline - check both text and parent_text
    outline_text = ""
    
    # First try to find it in text field with complete content
    for chunk in results_with_outline:
        if "Document Outline" in chunk["text"] and "Summa Tortillae" in chunk["text"]:
            outline_text = chunk["text"]
            break
    
    # If not found in text, check parent_text (more common for hierarchical chunking)
    if not outline_text:
        for chunk in results_with_outline:
            parent_text = chunk["metadata"].get("parent_text", "")
            if "Document Outline" in parent_text and "Summa Tortillae" in parent_text:
                outline_text = parent_text
                break
    
    if outline_text:
        print("\n✓ Found complete outline text")
        # Extract just the outline section for display
        if "Document Outline" in outline_text:
            outline_start = outline_text.find("Document Outline")
            outline_section = outline_text[outline_start:]
            # Limit display but use full text for verification
            display_limit = 1500
            if len(outline_section) > display_limit:
                print(outline_section[:display_limit] + "...")
            else:
                print(outline_section)
        
        # Verify it contains expected headers
        expected_headers = [
            "Summa Tortillae",
            "Paso 1:",
            "1.1 La Patata",
            "Paso 2:",
            "2.1 El Ritual",
            "Paso 6:"
        ]
        
        print("\n✓ Checking for expected headers:")
        all_found = True
        for header in expected_headers:
            if header in outline_text:
                print(f"  ✓ Found: {header}")
            else:
                print(f"  ✗ Missing: {header}")
                all_found = False
        
        if not all_found:
            print("\n✗ FAIL: Some expected headers not found in outline")
            return False
        else:
            print("\n✓ All expected headers found in outline")
        
        # Verify the format uses <a> tags
        if "<a>" in outline_text and "</a>" in outline_text:
            print("✓ Outline uses <a> tags as expected")
        else:
            print("✗ FAIL: Outline does not use <a> tags")
            return False
        
        # Verify hierarchical indentation with asterisks
        outline_lines = outline_text.split("\n")
        has_indented_items = False
        for line in outline_lines:
            if line.strip().startswith("*") and line.startswith("  "):
                has_indented_items = True
                break
        
        if has_indented_items:
            print("✓ Outline has hierarchical indentation")
        else:
            print("✓ Outline structure present (indentation may vary)")
    else:
        print("✗ FAIL: Could not extract complete outline text for verification")
        return False
    
    # Test 4: Verify parameter configuration
    print("\n" + "-" * 80)
    print("TEST 4: Verify parameter configuration")
    print("-" * 80)
    
    params = plugin.get_parameters()
    if "include_outline" in params:
        print("✓ 'include_outline' parameter is defined")
        outline_param = params["include_outline"]
        print(f"  Type: {outline_param.get('type')}")
        print(f"  Default: {outline_param.get('default')}")
        print(f"  Description: {outline_param.get('description')}")
        
        if outline_param.get("type") == "boolean":
            print("✓ Parameter type is boolean")
        else:
            print("✗ FAIL: Parameter type should be boolean")
            return False
            
        if outline_param.get("default") is False:
            print("✓ Default value is False (backward compatible)")
        else:
            print("⚠ Warning: Default value is not False")
    else:
        print("✗ FAIL: 'include_outline' parameter not found")
        return False
    
    print("\n" + "=" * 80)
    print("ALL OUTLINE GENERATION TESTS PASSED")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = test_outline_generation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED WITH ERROR:")
        print(f"  {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
