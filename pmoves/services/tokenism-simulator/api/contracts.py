"""
Contract API endpoints for PMOVES Tokenism Simulator.
"""
from flask import Blueprint, jsonify
from models.simulation import ContractType

contracts_bp = Blueprint('contracts', __name__)


def _get_contract_description(contract: ContractType) -> str:
    descriptions = {
        ContractType.GRO_TOKEN: 'Basic GroToken circulation contract',
        ContractType.FOOD_USD: 'FoodUSD stable-unit contract',
        ContractType.GROUP_PURCHASE: 'Group-purchase escrow contract',
        ContractType.GRO_VAULT: 'GroToken vault/savings contract',
        ContractType.COOP_GOVERNOR: 'Cooperative governance contract',
    }
    return descriptions.get(contract, 'Token economy contract')


@contracts_bp.route('/api/v1/contracts', methods=['GET'])
def list_contracts():
    """List available token economy contract types."""
    return jsonify({
        'contracts': [
            {
                'id': c.value,
                'name': c.value.replace('_', ' ').title(),
                'description': _get_contract_description(c),
            }
            for c in ContractType
        ]
    }), 200
