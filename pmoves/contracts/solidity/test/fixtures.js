const { ethers } = require("hardhat");
const { loadFixture, time } = require("@nomicfoundation/hardhat-network-helpers");

async function deployCoreFixture() {
  const [treasury, alice, bob, carol, supplier] = await ethers.getSigners();

  const FoodUSD = await ethers.getContractFactory("FoodUSD");
  const foodUSD = await FoodUSD.connect(treasury).deploy(treasury.address);
  await foodUSD.waitForDeployment();

  const GroToken = await ethers.getContractFactory("GroToken");
  const groToken = await GroToken.connect(treasury).deploy(treasury.address);
  await groToken.waitForDeployment();

  const GroVault = await ethers.getContractFactory("GroVault");
  const vault = await GroVault.deploy(groToken); // constructor expects IERC20
  await vault.waitForDeployment();

  const CoopGovernor = await ethers.getContractFactory("CoopGovernor");
  const votingPeriod = 7n * 24n * 60n * 60n; // one week
  const quorum = 50n;
  const governor = await CoopGovernor.deploy(vault, treasury.address, Number(votingPeriod), quorum);
  await governor.waitForDeployment();

  const GroupPurchase = await ethers.getContractFactory("GroupPurchase");
  const groupPurchase = await GroupPurchase.deploy(foodUSD);
  await groupPurchase.waitForDeployment();

  const baseGro = ethers.parseEther("10000");
  await groToken.connect(treasury).mint(alice.address, baseGro);
  await groToken.connect(treasury).mint(bob.address, baseGro / 2n);
  await groToken.connect(treasury).mint(carol.address, ethers.parseEther("2500"));

  const baseFood = ethers.parseEther("20000");
  await foodUSD.connect(treasury).mint(alice.address, baseFood);
  await foodUSD.connect(treasury).mint(bob.address, baseFood);
  await foodUSD.connect(treasury).mint(carol.address, baseFood);

  return {
    treasury,
    alice,
    bob,
    carol,
    supplier,
    foodUSD,
    groToken,
    vault,
    governor,
    groupPurchase,
    votingPeriod,
    quorum,
  };
}

module.exports = {
  loadFixture,
  time,
  deployCoreFixture,
};
