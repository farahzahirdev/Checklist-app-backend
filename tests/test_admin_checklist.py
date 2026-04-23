import uuid
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.models.checklist import ChecklistSection
from app.services.admin_checklist import reorder_sections


def test_admin_reorder_sections_service() -> None:
    """Test the reorder sections service function"""
    # Mock database session
    mock_db = MagicMock(spec=Session)
    
    # Test data
    checklist_id = uuid.uuid4()
    section_id1 = uuid.uuid4()
    section_id2 = uuid.uuid4()
    
    # Mock sections
    section1 = ChecklistSection(
        id=section_id1,
        checklist_id=checklist_id,
        section_code="SEC-1",
        display_order=1
    )
    section2 = ChecklistSection(
        id=section_id2,
        checklist_id=checklist_id,
        section_code="SEC-2",
        display_order=2
    )
    
    # Mock database queries
    mock_db.scalars.return_value.all.return_value = [section1, section2]
    
    # Mock checklist for version increment
    mock_checklist = MagicMock()
    mock_checklist.increment_version = MagicMock()
    mock_db.get.return_value = mock_checklist
    
    # Mock the latest translation function
    with patch("app.services.admin_checklist._latest_section_translation") as mock_translation:
        mock_translation.return_value = MagicMock(title="Test Section")
        
        # Mock the _to_section_response function
        with patch("app.services.admin_checklist._to_section_response") as mock_response:
            mock_response.return_value = {
                "id": section_id1,
                "checklist_id": checklist_id,
                "title": "Test Section",
                "order": 2
            }
            
            # Call the service function
            section_orders = [
                {"section_id": section_id1, "order": 2},
                {"section_id": section_id2, "order": 1}
            ]
            
            result = reorder_sections(
                db=mock_db,
                checklist_id=checklist_id,
                section_orders=section_orders
            )
            
            # Verify the sections were updated
            assert section1.display_order == 2
            assert section2.display_order == 1
            
            # Verify checklist version was incremented
            mock_checklist.increment_version.assert_called_once()
            
            # Verify commit was called
            mock_db.commit.assert_called_once()
            
            # Verify result is returned
            assert len(result) == 2
